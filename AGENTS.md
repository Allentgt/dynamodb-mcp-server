# AGENTS.md — dynamodb-mcp-server

## Project Overview

Python MCP (Model Context Protocol) server providing DynamoDB tools for LLM agents.
Built with FastMCP (Python SDK), managed by `uv`, targeting Python 3.14.

---

## Build & Run Commands

### Package Management (uv)

```bash
uv sync                     # Install dependencies from pyproject.toml
uv add <package>            # Add a dependency
uv add --dev <package>      # Add a dev dependency
uv run <command>            # Run command in the virtual environment
```

### Running the Server

```bash
uv run python main.py       # Run the MCP server (stdio transport)
```

> **WARNING**: MCP servers are long-running stdio processes. Running directly will hang.
> Use `timeout 5s uv run python main.py` for smoke tests, or test via the MCP inspector.

### Linting & Formatting

```bash
uv run ruff check .         # Lint all files
uv run ruff check --fix .   # Lint and auto-fix
uv run ruff format .        # Format all files
uv run ruff format --check .  # Check formatting without changes
uv run mypy .               # Type check (when configured)
```

### Testing (pytest)

```bash
uv run pytest               # Run all tests
uv run pytest tests/        # Run tests in specific directory
uv run pytest tests/test_tools.py  # Run a single test file
uv run pytest tests/test_tools.py::test_query_table  # Run a single test function
uv run pytest tests/test_tools.py::TestQueryTool  # Run a single test class
uv run pytest -x            # Stop on first failure
uv run pytest -v            # Verbose output
uv run pytest --tb=short    # Short tracebacks
```

### Syntax Verification (no test framework needed)

```bash
uv run python -m py_compile main.py   # Verify syntax without running
```

---

## Project Structure (Target)

```
dynamodb-mcp-server/
  main.py              # Server entry point — MCP server initialization and startup
  pyproject.toml       # Project config, dependencies, tool settings (ruff, mypy, pytest)
  .python-version      # Python 3.14
  tests/               # Test files (pytest)
    conftest.py        # Shared fixtures (mock DynamoDB client, sample data)
    test_*.py          # Test modules matching source modules
  src/                 # Source modules (if project grows beyond single file)
    tools/             # MCP tool implementations (one file per tool group)
    utils/             # Shared helpers (pagination, formatting, error handling)
```

---

## Code Style Guidelines

### Python Version & Features

- Target **Python 3.14** — use modern syntax freely
- Use `match` statements where appropriate (3.10+)
- Use `type` aliases with `type X = ...` syntax (3.12+)
- Use `|` union syntax: `str | None` not `Optional[str]`

### Imports

- Standard library first, blank line, third-party, blank line, local imports
- Use absolute imports, not relative
- Import specific names: `from typing import Any` not `import typing`
- Group MCP/FastMCP imports with third-party block

```python
import json
import logging
from typing import Any

import boto3
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from src.utils.pagination import paginate_results
```

### Naming Conventions

| Element         | Convention       | Example                    |
|-----------------|------------------|----------------------------|
| Files/modules   | snake_case       | `query_tools.py`           |
| Functions       | snake_case       | `scan_table()`             |
| Classes         | PascalCase       | `QueryInput`               |
| Constants       | UPPER_SNAKE_CASE | `MAX_ITEMS = 1000`         |
| MCP tool names  | snake_case       | `@mcp.tool("query_table")` |
| Private         | leading `_`      | `_build_filter()`          |

### Type Hints

- **Required on all function signatures** — parameters and return types
- Use `Pydantic BaseModel` for MCP tool input validation
- Use `Field(description=...)` for all model fields — these become tool parameter docs
- Never use `Any` unless interfacing with untyped external APIs

```python
class QueryInput(BaseModel):
    table_name: str = Field(description="DynamoDB table name")
    key_condition: str = Field(description="Key condition expression, e.g. 'PK = :pk'")
    limit: int = Field(default=25, ge=1, le=1000, description="Max items to return")

@mcp.tool("query_table")
async def query_table(input: QueryInput) -> str:
    """Query a DynamoDB table using key conditions. Returns matching items as JSON."""
    ...
```

### Async/Await

- All MCP tool handlers **must be async**
- All I/O operations (DynamoDB calls, file reads) use `await`
- Use `aioboto3` for async DynamoDB access (not synchronous `boto3`)

### Error Handling

- Return clear, actionable error messages — agents must understand what went wrong
- Never raise raw exceptions from tools; catch and return descriptive strings
- Suggest next steps in error messages when possible
- Log full tracebacks server-side; return clean messages to the agent

```python
try:
    response = await table.query(**params)
except ClientError as e:
    error_code = e.response["Error"]["Code"]
    if error_code == "ResourceNotFoundException":
        return f"Error: Table '{table_name}' not found. Use list_tables to see available tables."
    return f"Error querying table: {error_code} — {e.response['Error']['Message']}"
```

### Docstrings & Tool Descriptions

- Every MCP tool needs a comprehensive docstring — this is the agent's documentation
- First line: one-sentence summary of what the tool does
- Body: when to use it, parameter details, return format, usage examples
- Include "when NOT to use" guidance where helpful

### Constants

- Define at module level: `CHARACTER_LIMIT`, `DEFAULT_PAGE_SIZE`, `API_TIMEOUT`
- Do not hardcode values in function bodies

### Formatting

- **ruff** is the formatter and linter (configure in `pyproject.toml`)
- Line length: 100 (ruff default: 88 — set explicitly in pyproject.toml)
- Use trailing commas in multi-line structures
- Double quotes for strings (ruff default)

---

## MCP Server Design Principles

1. **Tools to use** — use firecrawl for documentation research and always use the mcp-builder skill for this project
2. **Build for workflows, not API wrappers** — combine related DynamoDB calls into useful tools
3. **Optimize for limited context** — return concise, high-signal data; support `format` param (json/markdown)
4. **Actionable errors** — every error message should tell the agent what to do next
5. **Truncation** — enforce `CHARACTER_LIMIT` (~25,000 chars) on large responses
6. **Pagination** — support `limit` and `next_token` parameters for large result sets
7. **Tool annotations** — set `readOnlyHint`, `destructiveHint`, `idempotentHint` on every tool

---

## Testing Strategy

- Use `pytest` with `pytest-asyncio` for async tool tests
- Mock DynamoDB with `moto` library — never hit real AWS in tests
- Test both success paths and error paths for every tool
- Fixtures in `conftest.py`: mock DynamoDB client, pre-populated tables

```python
@pytest.fixture
def dynamodb_table():
    with mock_dynamodb():
        client = boto3.resource("dynamodb", region_name="us-east-1")
        table = client.create_table(
            TableName="test-table",
            KeySchema=[{"AttributeName": "PK", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "PK", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield table
```

---

## Dependencies (Expected)

```toml
# pyproject.toml [project.dependencies]
dependencies = [
    "mcp[cli]",          # MCP Python SDK with CLI
    "aioboto3",          # Async AWS SDK
    "pydantic>=2.0",     # Input validation (included with mcp)
]

# [project.optional-dependencies] or [dependency-groups]
# dev dependencies
dev = [
    "pytest",
    "pytest-asyncio",
    "moto[dynamodb]",    # DynamoDB mocking
    "ruff",              # Linting + formatting
    "mypy",              # Type checking
]
```

---

## Common Pitfalls

- **Don't use synchronous boto3** in tool handlers — it blocks the event loop
- **Don't return raw DynamoDB responses** — format for agent consumption (strip metadata)
- **Don't suppress type errors** with `# type: ignore` — fix the types
- **Don't use `print()`** for logging — use `logging.getLogger(__name__)`
- **Don't run the server directly** in tests — use the MCP test client or mock at the tool level
