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
import os

from dynamodb_mcp_server.tools import table_management, item_operations, query_scan # noqa: F401
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
    parser.add_argument(
        "--region",
        default=None,
        help="AWS region (overrides AWS_REGION env var, default: us-east-1)",
    )
    parser.add_argument(
        "--endpoint-url",
        default=None,
        help="Custom endpoint URL for DynamoDB Local or LocalStack (overrides AWS_ENDPOINT_URL)",
    )
    return parser.parse_args()


def main() -> None:
    """Start the DynamoDB MCP server with the selected transport."""
    args = _parse_args()
    transport = TRANSPORT_ALIASES[args.transport]

    # Apply CLI overrides to environment (picked up by app_lifespan)
    if args.region is not None:
        os.environ["AWS_REGION"] = args.region
    if args.endpoint_url is not None:
        os.environ["AWS_ENDPOINT_URL"] = args.endpoint_url

    # Get values (either from env or CLI override)
    region = os.environ.get("AWS_REGION", "us-east-1")
    endpoint_url = os.environ.get("AWS_ENDPOINT_URL")

    if transport == "stdio":
        logger.info("Starting DynamoDB MCP server (stdio transport)")
    else:
        logger.info(
            "Starting DynamoDB MCP server on %s:%d%s",
            mcp.settings.host,
            mcp.settings.port,
            mcp.settings.streamable_http_path,
        )
    logger.info("Using region=%s, endpoint_url=%s", region, endpoint_url or "AWS (default)")

    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
