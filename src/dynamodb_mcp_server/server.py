"""MCP server instance and shared application context.

Separated from main.py to avoid circular imports when tool modules
register themselves via @mcp.tool.
"""

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import aioboto3
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)


@dataclass
class AppContext:
    """Shared application context available to all MCP tools via lifespan."""

    session: aioboto3.Session
    region: str
    endpoint_url: str | None = None


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Initialize shared resources for the MCP server lifecycle.

    Creates an aioboto3 session that all tools share for DynamoDB access.
    Region is determined from AWS_REGION env var, defaulting to us-east-1.
    Endpoint URL is read from AWS_ENDPOINT_URL for DynamoDB Local or LocalStack.
    """
    region = os.environ.get("AWS_REGION", "us-east-1")
    endpoint_url = os.environ.get("AWS_ENDPOINT_URL")
    session = aioboto3.Session(region_name=region)
    logger.info(
        "DynamoDB MCP server started — region=%s, endpoint_url=%s",
        region,
        endpoint_url or "AWS (default)",
    )
    try:
        yield AppContext(session=session, region=region, endpoint_url=endpoint_url)
    finally:
        logger.info("DynamoDB MCP server shutting down")


mcp = FastMCP(
    "DynamoDB MCP Server",
    lifespan=app_lifespan,
    json_response=True,
    host=os.environ.get("MCP_HOST", "0.0.0.0"),
    port=int(os.environ.get("MCP_PORT", "8008")),
    streamable_http_path=os.environ.get("MCP_PATH", "/mcp"),
)
