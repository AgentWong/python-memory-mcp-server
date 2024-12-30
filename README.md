# Memory MCP Server

An implementation of the Model Context Protocol (MCP) server for managing Claude's memory and knowledge graph.

## Installation

You can install the package using Python:

```bash
python -m pip install git+https://github.com/estav/python-memory-mcp-server.git
```

Or using `uv`:

```bash
uvx memory-mcp-server
```

## Usage

Once installed, you can run the server using Python:

```bash
python -m memory_mcp_server
```

Or with `uv`:

```bash
uvx memory-mcp-server
```

### Configuration

The server expects certain environment variables to be set:
- `DATABASE_URL`: SQLite database URL for storing the knowledge graph. Supports both absolute paths (e.g., `sqlite:////home/jdoe/claude.db`) and relative paths (e.g., `sqlite:///memory.db`)

### Integration with Claude Desktop

To use this MCP server with Claude Desktop, add the following to your `claude_desktop_config.json`:

Using Python:
```json
{
  "mcpServers": {
    "memory": {
      "command": "python",
      "args": ["-m", "memory_mcp_server"],
      "env": {
        "DATABASE_URL": "sqlite:////home/jdoe/claude.db"
      }
    }
  }
}
```

Using `uv`:
```json
{
  "mcpServers": {
    "memory": {
      "command": "uvx",
      "args": ["memory-mcp-server"],
      "env": {
        "DATABASE_URL": "sqlite:///memory.db"
      }
    }
  }
}
```

## Development

1. Clone the repository:
```bash
git clone https://github.com/estav/python-memory-mcp-server.git
cd python-memory-mcp-server
```

2. Create a virtual environment and install dependencies:
```bash
uv venv
source .venv/bin/activate
uv pip install -e ".[test]"  # Include test dependencies
```

3. Run tests:
```bash
pytest                    # Run all tests
pytest -v                # Run with verbose output
pytest -v --cov         # Run with coverage report
```

4. Run the server locally:
```bash
python -m memory_mcp_server
```

## Testing

The project uses pytest for testing. The test suite includes:

### Unit Tests
- `test_knowledge_graph_manager.py`: Tests for basic knowledge graph operations
- `test_optimized_knowledge_graph_manager.py`: Tests for optimized/batch operations
- `test_server.py`: Tests for MCP server implementation

### Running Tests
```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=memory_mcp_server

# Run specific test file
pytest tests/test_server.py

# Run tests with verbose output
pytest -v
```

### Test Fixtures
The `conftest.py` file provides common test fixtures:
- `temp_db_path`: Creates a temporary SQLite database
- `knowledge_graph_manager`: Provides a KnowledgeGraphManager instance
- `optimized_knowledge_graph_manager`: Provides an OptimizedKnowledgeGraphManager instance

## License

This project is licensed under the MIT License - see the LICENSE file for details.
