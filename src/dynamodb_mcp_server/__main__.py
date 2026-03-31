"""DynamoDB MCP Server entry point.

Supports both ``python -m dynamodb_mcp_server`` and the
``dynamodb-mcp-server`` console script installed by pip/uv.

Transport modes:
    stdio (default)  — for local use with uvx / Claude Desktop / Cursor
    streamable-http  — for remote deployment as an HTTP server

Usage:
    dynamodb-mcp-server                    # stdio (default)
    dynamodb-mcp-server --transport stdio  # explicit stdio
    dynamodb-mcp-server --transport http   # streamable HTTP
"""

import argparse
import logging

import dynamodb_mcp_server.tools.table_management  # noqa: F401
from dynamodb_mcp_server.server import mcp

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

TRANSPORT_ALIASES: dict[str, str] = {
    "stdio": "stdio",
    "http": "streamable-http",
    "streamable-http": "streamable-http",
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="DynamoDB MCP Server")
    parser.add_argument(
        "--transport",
        choices=list(TRANSPORT_ALIASES),
        default="stdio",
        help="Transport mode: stdio (default, for uvx/local) or http (remote deployment)",
    )
    return parser.parse_args()


def main() -> None:
    """Start the DynamoDB MCP server with the selected transport."""
    args = _parse_args()
    transport = TRANSPORT_ALIASES[args.transport]

    if transport == "stdio":
        logger.info("Starting DynamoDB MCP server (stdio transport)")
    else:
        logger.info(
            "Starting DynamoDB MCP server on %s:%d%s",
            mcp.settings.host,
            mcp.settings.port,
            mcp.settings.streamable_http_path,
        )

    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
