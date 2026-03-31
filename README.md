# dynamodb-mcp-server

An MCP (Model Context Protocol) server that gives LLM agents full access to Amazon DynamoDB. Built with [FastMCP](https://github.com/jlowin/fastmcp) and [aioboto3](https://github.com/terrycain/aioboto3), it exposes 11 tools covering table management, querying, scanning, and item CRUD operations. Supports both **stdio** (for `uvx` / local clients) and **streamable HTTP** (for remote deployment).

## Features

- **11 DynamoDB tools** — list, describe, create table, query, scan, create GSI, add/update/delete items, bulk add, prune
- **Dual transport** — stdio (default, for `uvx` / Claude Desktop / Cursor) and streamable HTTP (for remote deployment)
- **Async end-to-end** — aioboto3 for non-blocking DynamoDB access
- **Structured input validation** — Pydantic models with field descriptions that become tool parameter docs
- **Dual output formats** — JSON or Markdown, controlled per request
- **Pagination** — `limit` and `next_token` on all read operations
- **Response truncation** — enforces a 25,000 character limit to stay within LLM context windows
- **Actionable errors** — every error message tells the agent what to do next
- **Tool annotations** — `readOnlyHint`, `destructiveHint`, `idempotentHint` on every tool
- **DynamoDB Local / LocalStack support** — connect to local instances via `AWS_ENDPOINT_URL`

## Quick Start

### Prerequisites

- Python 3.14+
- [uv](https://docs.astral.sh/uv/) package manager
- AWS credentials configured (via environment variables, `~/.aws/credentials`, or IAM role)

### Install and Run

```bash
# Clone the repository
git clone https://github.com/Allentgt/dynamodb-mcp-server.git
cd dynamodb-mcp-server

# Install dependencies
uv sync

# Run the server (stdio transport, default)
uv run dynamodb-mcp-server

# Run with HTTP transport for remote deployment
uv run dynamodb-mcp-server --transport http
```

The default transport is **stdio** (for local MCP clients). Use `--transport http` to start a streamable HTTP server on `http://0.0.0.0:8008/mcp`.

### Install via uvx (no clone needed)

```bash
uvx --from git+https://github.com/Allentgt/dynamodb-mcp-server.git dynamodb-mcp-server
```

### Install from Wheel

```bash
# Build the package
uv build

# Install the wheel
uv pip install dist/dynamodb_mcp_server-0.1.0-py3-none-any.whl

# Run via console script
dynamodb-mcp-server
```

## Configuration

All configuration is via environment variables:

| Variable | Default | Description |
|---|---|---|
| `AWS_REGION` | `us-east-1` | AWS region for DynamoDB |
| `AWS_ACCESS_KEY_ID` | — | AWS access key (or use IAM role) |
| `AWS_SECRET_ACCESS_KEY` | — | AWS secret key (or use IAM role) |
| `AWS_ENDPOINT_URL` | — | Custom endpoint for DynamoDB Local or LocalStack |
| `MCP_HOST` | `0.0.0.0` | Server bind address |
| `MCP_PORT` | `8000` | Server port |
| `MCP_PATH` | `/mcp` | Streamable HTTP endpoint path |

### Using with DynamoDB Local

```bash
# Start DynamoDB Local (Docker)
docker run -p 8000:8000 amazon/dynamodb-local

# Point the MCP server at it (use a different port to avoid conflict)
$env:AWS_ENDPOINT_URL = "http://localhost:8000"  # PowerShell
export AWS_ENDPOINT_URL="http://localhost:8000"   # Bash

$env:MCP_PORT = "8001"  # PowerShell
export MCP_PORT=8001     # Bash

uv run dynamodb-mcp-server
```

### MCP Client Configuration

**Recommended: stdio via `uvx`** (Claude Desktop, Cursor, etc.)

```json
{
  "mcpServers": {
    "dynamodb": {
      "command": "uvx",
      "args": [
        "--from", "git+https://github.com/Allentgt/dynamodb-mcp-server.git",
        "dynamodb-mcp-server"
      ],
      "env": {
        "AWS_REGION": "us-east-1",
        "AWS_ACCESS_KEY_ID": "your-key",
        "AWS_SECRET_ACCESS_KEY": "your-secret"
      }
    }
  }
}
```

**Alternative: remote HTTP server**

```json
{
  "mcpServers": {
    "dynamodb": {
      "url": "http://localhost:8008/mcp"
    }
  }
}
```

## Tools

### Table Management

| Tool | Description | Annotations |
|---|---|---|
| `list_tables` | List all DynamoDB tables in the configured region. Supports pagination. | read-only, idempotent |
| `describe_table` | Get table schema, key definitions, GSIs/LSIs, billing mode, item count, and size. | read-only, idempotent |
| `create_table` | Create a new table with partition key, optional sort key, and billing mode. | mutating, not idempotent |
| `create_gsi` | Create a Global Secondary Index on a table. Specify key schema and projection type. | mutating, not idempotent |

### Query & Scan

| Tool | Description | Annotations |
|---|---|---|
| `query_table` | Query by key condition expression. Supports GSI/LSI, filter expressions, pagination, and JSON/Markdown output. | read-only, idempotent |
| `scan_table` | Full table scan with optional filter expression. Supports pagination and JSON/Markdown output. | read-only, idempotent |

### Item Operations

| Tool | Description | Annotations |
|---|---|---|
| `add_item` | Put a single item. Supports condition expressions to prevent overwrites. | mutating, idempotent |
| `update_item` | Update specific attributes with SET, REMOVE, ADD, DELETE expressions. Returns the updated item. | mutating, idempotent |
| `delete_item` | Delete a single item by primary key. | destructive, idempotent |
| `bulk_add_items` | Batch write up to 500 items using DynamoDB batch_writer with automatic retry. | mutating, idempotent |
| `prune_table` | Delete all (or filtered) items from a table. Requires `confirm=true` as a safety guard. | destructive, not idempotent |

## Tool Usage Examples

### List tables

```json
{ "limit": 10 }
```

### Create a table

```json
{
  "table_name": "orders",
  "partition_key": "PK",
  "sort_key": "SK",
  "sort_key_type": "S",
  "billing_mode": "PAY_PER_REQUEST"
}
```

### Query with key condition

```json
{
  "table_name": "orders",
  "key_condition_expression": "PK = :pk AND begins_with(SK, :prefix)",
  "expression_attribute_values": { ":pk": "USER#123", ":prefix": "ORDER#" },
  "format": "markdown"
}
```

### Add an item with overwrite protection

```json
{
  "table_name": "users",
  "item": { "PK": "USER#456", "name": "Alice", "email": "alice@example.com" },
  "condition_expression": "attribute_not_exists(PK)"
}
```

### Update specific attributes

```json
{
  "table_name": "users",
  "key": { "PK": "USER#456" },
  "update_expression": "SET #n = :name, email = :email",
  "expression_attribute_names": { "#n": "name" },
  "expression_attribute_values": { ":name": "Bob", ":email": "bob@example.com" }
}
```

### Bulk add items

```json
{
  "table_name": "products",
  "items": [
    { "PK": "PROD#1", "name": "Widget", "price": 9.99 },
    { "PK": "PROD#2", "name": "Gadget", "price": 19.99 }
  ]
}
```

### Prune table (with safety confirmation)

```json
{
  "table_name": "logs",
  "confirm": true,
  "filter_expression": "created_at < :cutoff",
  "expression_attribute_values": { ":cutoff": "2024-01-01" }
}
```

## Project Structure

```
dynamodb-mcp-server/
  src/dynamodb_mcp_server/
    __init__.py
    __main__.py          # Entry point — registers tools, starts server
    server.py            # FastMCP instance, AppContext, lifespan
    models.py            # Pydantic input models for all 10 tools
    utils.py             # JSON encoding, error handling, truncation, formatting
    tools/
      __init__.py
      table_management.py  # list_tables, describe_table, create_gsi
      query_scan.py        # query_table, scan_table
      item_operations.py   # add_item, delete_item, update_item, bulk_add_items, prune_table
  tests/
    conftest.py            # Async mock wrappers over moto, fixtures
    test_table_management.py
    test_query_scan.py
    test_item_operations.py
    test_utils.py
  main.py                  # Backward-compat shim
  pyproject.toml
  AGENTS.md
```

## Development

### Setup

```bash
uv sync  # Installs all dependencies including dev group
```

### Running Tests

```bash
uv run pytest           # Run all 72 tests
uv run pytest -x        # Stop on first failure
uv run pytest -v        # Verbose output
uv run pytest tests/test_query_scan.py::test_query_table  # Single test
```

Tests use [moto](https://github.com/getmoto/moto) to mock DynamoDB locally. No AWS credentials or network access required.

### Linting & Formatting

```bash
uv run ruff check .         # Lint
uv run ruff check --fix .   # Lint with auto-fix
uv run ruff format .        # Format
uv run ruff format --check . # Check formatting
```

### Building

```bash
uv build  # Produces .tar.gz and .whl in dist/
```

## Architecture Notes

- **Transport**: Stdio (default) for local clients like `uvx`, Claude Desktop, Cursor. Streamable HTTP (`--transport http`) for remote/shared deployments
- **Async**: All tool handlers are async. DynamoDB calls go through aioboto3 to avoid blocking the event loop
- **Lifespan pattern**: `app_lifespan()` creates a shared `aioboto3.Session` stored in `AppContext`, available to all tools via `ctx.request_context.lifespan_context`
- **Error handling**: `ClientError` exceptions are caught and mapped to actionable messages (e.g., "Table not found — use list_tables to see available tables")
- **Response formatting**: Tools support `format` parameter (`json` or `markdown`). Markdown tables are generated for scan/query results
- **Truncation**: Responses exceeding 25,000 characters are truncated with a warning and suggestion to use pagination

## License

MIT
