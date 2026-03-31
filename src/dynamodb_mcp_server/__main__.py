"""DynamoDB MCP Server entry point.

Supports both ``python -m dynamodb_mcp_server`` and the
``dynamodb-mcp-server`` console script installed by pip/uv.
"""

import logging

import dynamodb_mcp_server.tools.item_operations
import dynamodb_mcp_server.tools.query_scan
import dynamodb_mcp_server.tools.table_management  # noqa: F401
from dynamodb_mcp_server.server import mcp

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main() -> None:
    """Start the DynamoDB MCP server with streamable HTTP transport."""
    logger.info(
        "Starting DynamoDB MCP server on %s:%d%s",
        mcp.settings.host,
        mcp.settings.port,
        mcp.settings.streamable_http_path,
    )
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
