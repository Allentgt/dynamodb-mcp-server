"""MCP tools for DynamoDB table management operations.

Includes: list_tables, describe_table, create_gsi
"""

import logging
from typing import Any

from botocore.exceptions import ClientError
from mcp.server.fastmcp import Context
from mcp.server.session import ServerSession
from mcp.types import ToolAnnotations

from dynamodb_mcp_server.models import CreateGsiInput, DescribeTableInput, ListTablesInput
from dynamodb_mcp_server.server import AppContext, mcp
from dynamodb_mcp_server.utils import handle_client_error, to_json, truncate_response

logger = logging.getLogger(__name__)


@mcp.tool(
    name="list_tables",
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def list_tables(
    input: ListTablesInput,
    ctx: Context[ServerSession, AppContext],
) -> str:
    """List all DynamoDB tables in the configured AWS region.

    Returns table names with pagination support. Use this as a starting point
    to discover available tables before querying or scanning.

    When to use:
    - To discover which tables exist in the account
    - To find a table name before using describe_table, query_table, or scan_table

    Returns:
        JSON with 'table_names' list, 'count', and optional 'next_table_name' for pagination.
    """
    app_ctx = ctx.request_context.lifespan_context
    params: dict[str, Any] = {"Limit": input.limit}
    if input.exclusive_start_table_name:
        params["ExclusiveStartTableName"] = input.exclusive_start_table_name

    try:
        async with app_ctx.session.client("dynamodb", endpoint_url=app_ctx.endpoint_url) as client:
            response = await client.list_tables(**params)
    except ClientError as e:
        return handle_client_error(e, "list_tables")

    table_names = response.get("TableNames", [])
    last_table = response.get("LastEvaluatedTableName")

    result: dict[str, Any] = {
        "table_names": table_names,
        "count": len(table_names),
        "has_more": last_table is not None,
    }
    if last_table:
        result["next_table_name"] = last_table

    return truncate_response(to_json(result))


@mcp.tool(
    name="describe_table",
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def describe_table(
    input: DescribeTableInput,
    ctx: Context[ServerSession, AppContext],
) -> str:
    """Get detailed information about a DynamoDB table's schema and configuration.

    Returns key schema, attribute definitions, GSIs/LSIs, billing mode,
    item count, table size, and table status.

    When to use:
    - To understand a table's key schema before querying
    - To check what GSIs exist before creating a new one
    - To verify table status (ACTIVE, CREATING, UPDATING, etc.)
    - To check item count and table size

    When NOT to use:
    - To list tables (use list_tables instead)

    Returns:
        JSON with table name, status, key schema, attribute definitions,
        indexes, billing mode, item count, and size in bytes.
    """
    app_ctx = ctx.request_context.lifespan_context
    try:
        async with app_ctx.session.client("dynamodb", endpoint_url=app_ctx.endpoint_url) as client:
            response = await client.describe_table(TableName=input.table_name)
    except ClientError as e:
        return handle_client_error(e, "describe_table", input.table_name)

    table = response["Table"]
    result: dict[str, Any] = {
        "table_name": table["TableName"],
        "status": table["TableStatus"],
        "key_schema": table["KeySchema"],
        "attribute_definitions": table["AttributeDefinitions"],
        "item_count": table.get("ItemCount", 0),
        "table_size_bytes": table.get("TableSizeBytes", 0),
        "billing_mode": table.get("BillingModeSummary", {}).get("BillingMode", "PROVISIONED"),
        "creation_date": str(table.get("CreationDateTime", "")),
    }

    if "GlobalSecondaryIndexes" in table:
        result["global_secondary_indexes"] = [
            {
                "index_name": gsi["IndexName"],
                "key_schema": gsi["KeySchema"],
                "projection": gsi["Projection"],
                "status": gsi["IndexStatus"],
                "item_count": gsi.get("ItemCount", 0),
            }
            for gsi in table["GlobalSecondaryIndexes"]
        ]

    if "LocalSecondaryIndexes" in table:
        result["local_secondary_indexes"] = [
            {
                "index_name": lsi["IndexName"],
                "key_schema": lsi["KeySchema"],
                "projection": lsi["Projection"],
            }
            for lsi in table["LocalSecondaryIndexes"]
        ]

    return truncate_response(to_json(result))


@mcp.tool(
    name="create_gsi",
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    ),
)
async def create_gsi(
    input: CreateGsiInput,
    ctx: Context[ServerSession, AppContext],
) -> str:
    """Create a Global Secondary Index (GSI) on a DynamoDB table.

    GSIs enable querying on non-primary-key attributes. The table must be
    in ACTIVE status. Index creation is asynchronous — use describe_table
    to monitor progress.

    When to use:
    - To enable queries on attributes that aren't part of the primary key
    - To create alternative access patterns for existing data

    When NOT to use:
    - If a suitable GSI already exists (check with describe_table first)
    - If the table is not in ACTIVE status

    Returns:
        JSON confirming the GSI creation was initiated with index details.
    """
    app_ctx = ctx.request_context.lifespan_context

    key_schema = [{"AttributeName": input.partition_key, "KeyType": "HASH"}]
    attr_defs = [{"AttributeName": input.partition_key, "AttributeType": input.partition_key_type}]

    if input.sort_key:
        key_schema.append({"AttributeName": input.sort_key, "KeyType": "RANGE"})
        attr_defs.append({"AttributeName": input.sort_key, "AttributeType": input.sort_key_type})

    projection: dict[str, Any] = {"ProjectionType": input.projection_type}
    if input.projection_type == "INCLUDE" and input.non_key_attributes:
        projection["NonKeyAttributes"] = input.non_key_attributes

    gsi_update: dict[str, Any] = {
        "Create": {
            "IndexName": input.index_name,
            "KeySchema": key_schema,
            "Projection": projection,
        }
    }

    try:
        async with app_ctx.session.client("dynamodb", endpoint_url=app_ctx.endpoint_url) as client:
            await client.update_table(
                TableName=input.table_name,
                AttributeDefinitions=attr_defs,
                GlobalSecondaryIndexUpdates=[gsi_update],
            )
    except ClientError as e:
        return handle_client_error(e, "create_gsi", input.table_name)

    result = {
        "message": f"GSI '{input.index_name}' creation initiated on table '{input.table_name}'.",
        "index_name": input.index_name,
        "key_schema": key_schema,
        "projection": projection,
        "status": "CREATING",
        "next_step": "Use describe_table to monitor the index creation progress.",
    }
    return to_json(result)
