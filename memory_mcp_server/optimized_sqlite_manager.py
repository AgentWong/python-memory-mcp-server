import sqlite3
import logging
import os
from typing import List, Optional, Dict, Any
from pathlib import Path
from urllib.parse import urlparse

from .interfaces import Entity, Relation
from .exceptions import EntityNotFoundError, EntityAlreadyExistsError

logger = logging.getLogger(__name__)

class OptimizedSQLiteManager:
    def __init__(self, database_url: str, echo: bool = False):
        """Initialize SQLite manager with database path extracted from URL."""
        parsed_url = urlparse(database_url)
        if not parsed_url.path:
            raise ValueError("Database path not specified in URL")
            
        # Handle the database path, supporting both absolute and relative paths
        path = parsed_url.path.lstrip('/')
        if '/' in path:  # If path contains directories
            self.db_path = str(Path(path).absolute())
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        else:  # Simple filename in current directory
            self.db_path = path
        self.echo = echo
        self._conn: Optional[sqlite3.Connection] = None

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create SQLite connection."""
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    async def initialize(self):
        """Initialize database schema."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Create entities table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS entities (
                name TEXT PRIMARY KEY,
                entity_type TEXT NOT NULL,
                observations TEXT NOT NULL
            )
        """)
        
        # Create relations table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS relations (
                from_entity TEXT NOT NULL,
                to_entity TEXT NOT NULL,
                relation_type TEXT NOT NULL,
                PRIMARY KEY (from_entity, to_entity, relation_type),
                FOREIGN KEY (from_entity) REFERENCES entities(name),
                FOREIGN KEY (to_entity) REFERENCES entities(name)
            )
        """)
        
        # Create indices
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_entity_type ON entities(entity_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_from_entity ON relations(from_entity)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_to_entity ON relations(to_entity)")
        
        conn.commit()

    async def cleanup(self):
        """Clean up database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    async def create_entities(self, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Create multiple new entities in the database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        created_entities = []

        for entity_data in entities:
            # Convert dict to Entity object
            entity = Entity.from_dict(entity_data)
            try:
                cursor.execute(
                    "INSERT INTO entities (name, entity_type, observations) VALUES (?, ?, ?)",
                    (entity.name, entity.entityType, ','.join(entity.observations))
                )
                created_entities.append(entity.to_dict())
            except sqlite3.IntegrityError:
                conn.rollback()
                raise EntityAlreadyExistsError(entity.name)

        conn.commit()
        return created_entities

    async def create_relations(self, relations_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Create multiple new relations in the database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        created_relations = []

        try:
            for relation_data in relations_data:
                # Convert dictionary to Relation object
                relation = Relation.from_dict(relation_data)
                
                # Verify both entities exist
                cursor.execute("SELECT 1 FROM entities WHERE name = ?", (relation.from_,))
                if not cursor.fetchone():
                    raise EntityNotFoundError(relation.from_)
                
                cursor.execute("SELECT 1 FROM entities WHERE name = ?", (relation.to,))
                if not cursor.fetchone():
                    raise EntityNotFoundError(relation.to)

                # Insert relation
                cursor.execute("""
                    INSERT INTO relations (from_entity, to_entity, relation_type) 
                    VALUES (?, ?, ?)
                    ON CONFLICT DO NOTHING
                """, (relation.from_, relation.to, relation.relationType))
                
                if cursor.rowcount > 0:
                    created_relations.append(relation.to_dict())

            conn.commit()
            return created_relations
            
        except Exception as e:
            conn.rollback()
            raise e

    async def read_graph(self) -> Dict[str, List[Dict[str, Any]]]:
        """Read the entire graph and return serializable format."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Get all entities
        cursor.execute("SELECT * FROM entities")
        entities = []
        for row in cursor.fetchall():
            entity = Entity(
                name=row['name'],
                entityType=row['entity_type'],
                observations=row['observations'].split(',') if row['observations'] else []
            )
            entities.append(entity.to_dict())

        # Get all relations
        cursor.execute("SELECT * FROM relations")
        relations = []
        for row in cursor.fetchall():
            relation = Relation(
                from_=row['from_entity'],
                to=row['to_entity'],
                relationType=row['relation_type']
            )
            relations.append(relation.to_dict())

        return {"entities": entities, "relations": relations}

    async def add_observations(self, observations: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        """Add new observations to existing entities."""
        conn = self._get_connection()
        cursor = conn.cursor()
        added_observations = {}

        for obs in observations:
            entity_name = obs["entityName"]
            new_contents = obs["contents"]

            # Check if entity exists
            cursor.execute("SELECT observations FROM entities WHERE name = ?", (entity_name,))
            result = cursor.fetchone()
            if not result:
                raise EntityNotFoundError(entity_name)

            # Get current observations and add new ones
            current_obs = result['observations'].split(',') if result['observations'] else []
            current_obs.extend(new_contents)
            
            # Update entity with new observations
            cursor.execute(
                "UPDATE entities SET observations = ? WHERE name = ?",
                (','.join(current_obs), entity_name)
            )
            added_observations[entity_name] = new_contents

        conn.commit()
        return added_observations

    async def delete_entities(self, entityNames: List[str]) -> None:
        """Remove entities and their relations."""
        conn = self._get_connection()
        cursor = conn.cursor()

        for name in entityNames:
            # Delete relations involving the entity
            cursor.execute(
                "DELETE FROM relations WHERE from_entity = ? OR to_entity = ?",
                (name, name)
            )
            # Delete the entity
            cursor.execute("DELETE FROM entities WHERE name = ?", (name,))

        conn.commit()

    async def delete_observations(self, deletions: List[Dict[str, Any]]) -> None:
        """Remove specific observations from entities."""
        conn = self._get_connection()
        cursor = conn.cursor()

        for deletion in deletions:
            entity_name = deletion["entityName"]
            to_delete = set(deletion["observations"])

            # Get current observations
            cursor.execute("SELECT observations FROM entities WHERE name = ?", (entity_name,))
            result = cursor.fetchone()
            if result:
                current_obs = result['observations'].split(',') if result['observations'] else []
                # Remove specified observations
                updated_obs = [obs for obs in current_obs if obs not in to_delete]
                
                # Update entity with remaining observations
                cursor.execute(
                    "UPDATE entities SET observations = ? WHERE name = ?",
                    (','.join(updated_obs), entity_name)
                )

        conn.commit()

    async def delete_relations(self, relations: List[Dict[str, Any]]) -> None:
        """Remove specific relations from the graph."""
        conn = self._get_connection()
        cursor = conn.cursor()

        for relation in relations:
            # Convert dictionary to Relation object for consistent handling
            relation_obj = Relation.from_dict(relation)
            cursor.execute(
                "DELETE FROM relations WHERE from_entity = ? AND to_entity = ? AND relation_type = ?",
                (relation_obj.from_, relation_obj.to, relation_obj.relationType)
            )

        conn.commit()

    async def open_nodes(self, names: List[str]) -> Dict[str, List[Dict[str, Any]]]:
        """Retrieve specific nodes by name and their relations in serializable format."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Get requested entities
        placeholders = ','.join('?' * len(names))
        cursor.execute(
            f"SELECT * FROM entities WHERE name IN ({placeholders})",
            names
        )
        
        entities = []
        for row in cursor.fetchall():
            entity = Entity(
                name=row['name'],
                entityType=row['entity_type'],
                observations=row['observations'].split(',') if row['observations'] else []
            )
            entities.append(entity.to_dict())

        # Get relations between requested entities
        cursor.execute(
            f"""
            SELECT * FROM relations 
            WHERE from_entity IN ({placeholders})
            AND to_entity IN ({placeholders})
            """,
            names * 2
        )

        relations = []
        for row in cursor.fetchall():
            relation = Relation(
                from_=row['from_entity'],
                to=row['to_entity'],
                relationType=row['relation_type']
            )
            relations.append(relation.to_dict())

        return {"entities": entities, "relations": relations}

    async def search_nodes(self, query: str) -> Dict[str, List[Dict[str, Any]]]:
        """Search for nodes and return serializable format."""
        if not query:
            raise ValueError("Search query cannot be empty")

        conn = self._get_connection()
        cursor = conn.cursor()
        search_pattern = f"%{query}%"

        # Search entities
        cursor.execute("""
            SELECT * FROM entities 
            WHERE name LIKE ? 
            OR entity_type LIKE ? 
            OR observations LIKE ?
        """, (search_pattern, search_pattern, search_pattern))
        
        entities = []
        entity_names = set()
        for row in cursor.fetchall():
            entity = Entity(
                name=row['name'],
                entityType=row['entity_type'],
                observations=row['observations'].split(',') if row['observations'] else []
            )
            entities.append(entity.to_dict())
            entity_names.add(entity.name)

        # Get related relations
        cursor.execute("""
            SELECT * FROM relations 
            WHERE from_entity IN (SELECT name FROM entities WHERE name IN ({}))
            AND to_entity IN (SELECT name FROM entities WHERE name IN ({}))
        """.format(
            ','.join('?' * len(entity_names)),
            ','.join('?' * len(entity_names))
        ), list(entity_names) * 2)

        relations = []
        for row in cursor.fetchall():
            relation = Relation(
                from_=row['from_entity'],
                to=row['to_entity'],
                relationType=row['relation_type']
            )
            relations.append(relation.to_dict())

        return {"entities": entities, "relations": relations}
