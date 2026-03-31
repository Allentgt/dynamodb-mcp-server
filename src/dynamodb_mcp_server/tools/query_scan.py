"""MCP tools for DynamoDB query and scan operations.

Includes: query_table, scan_table
"""

import logging
from typing import Any

from botocore.exceptions import ClientError
from mcp.server.fastmcp import Context
from mcp.server.session import ServerSession
from mcp.types import ToolAnnotations

from dynamodb_mcp_server.models import QueryTableInput, ScanTableInput
from dynamodb_mcp_server.server import AppContext, mcp
from dynamodb_mcp_server.utils import build_query_response, handle_client_error

logger = logging.getLogger(__name__)


@mcp.tool(
    name="query_table",
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def query_table(
    input: QueryTableInput,
    ctx: Context[ServerSession, AppContext],
) -> str:
    """Query a DynamoDB table using key conditions to find matching items.

    Queries are efficient because they use the table's primary key or GSI/LSI keys.
    Results are returned sorted by sort key. Optional filter expressions can
    further refine results (but don't reduce read capacity consumed).

    When to use:
    - To find items by primary key (partition key + optional sort key condition)
    - To find items using a GSI or LSI
    - When you know the partition key value

    When NOT to use:
    - When you don't know the partition key (use scan_table instead)
    - For full-table searches (use scan_table with filter)

    Returns:
        Items matching the query with count, scanned_count, and pagination key.
        Format controlled by 'format' parameter (json or markdown).
    """
    app_ctx = ctx.request_context.lifespan_context

    params: dict[str, Any] = {
        "KeyConditionExpression": input.key_condition_expression,
        "ExpressionAttributeValues": input.expression_attribute_values,
        "Limit": input.limit,
        "ScanIndexForward": input.scan_index_forward,
    }

    if input.filter_expression:
        params["FilterExpression"] = input.filter_expression
    if input.expression_attribute_names:
        params["ExpressionAttributeNames"] = input.expression_attribute_names
    if input.index_name:
        params["IndexName"] = input.index_name
    if input.exclusive_start_key:
        params["ExclusiveStartKey"] = input.exclusive_start_key

    try:
        async with app_ctx.session.resource(
            "dynamodb", endpoint_url=app_ctx.endpoint_url
        ) as resource:
            table = await resource.Table(input.table_name)
            response = await table.query(**params)
    except ClientError as e:
        return handle_client_error(e, "query_table", input.table_name)

    return build_query_response(
        items=response.get("Items", []),
        count=response.get("Count", 0),
        scanned_count=response.get("ScannedCount", 0),
        last_evaluated_key=response.get("LastEvaluatedKey"),
        fmt=input.format,
    )


@mcp.tool(
    name="scan_table",
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def scan_table(
    input: ScanTableInput,
    ctx: Context[ServerSession, AppContext],
) -> str:
    """Scan a DynamoDB table to read all items, optionally filtering results.

    Scans read every item in the table (or index), consuming read capacity
    proportional to table size regardless of filters. Use queries when possible.

    When to use:
    - To browse all items in a table
    - When you don't know the partition key value
    - For ad-hoc searches across all items

    When NOT to use:
    - When you know the partition key (use query_table — much more efficient)
    - For large tables without filters (expensive and slow)

    Returns:
        Items from the scan with count, scanned_count, and pagination key.
        Format controlled by 'format' parameter (json or markdown).
    """
    app_ctx = ctx.request_context.lifespan_context

    params: dict[str, Any] = {"Limit": input.limit}

    if input.filter_expression:
        params["FilterExpression"] = input.filter_expression
    if input.expression_attribute_values:
        params["ExpressionAttributeValues"] = input.expression_attribute_values
    if input.expression_attribute_names:
        params["ExpressionAttributeNames"] = input.expression_attribute_names
    if input.index_name:
        params["IndexName"] = input.index_name
    if input.exclusive_start_key:
        params["ExclusiveStartKey"] = input.exclusive_start_key

    try:
        async with app_ctx.session.resource(
            "dynamodb", endpoint_url=app_ctx.endpoint_url
        ) as resource:
            table = await resource.Table(input.table_name)
            response = await table.scan(**params)
    except ClientError as e:
        return handle_client_error(e, "scan_table", input.table_name)

    return build_query_response(
        items=response.get("Items", []),
        count=response.get("Count", 0),
        scanned_count=response.get("ScannedCount", 0),
        last_evaluated_key=response.get("LastEvaluatedKey"),
        fmt=input.format,
    )
