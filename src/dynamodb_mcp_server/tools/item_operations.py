"""MCP tools for DynamoDB item-level operations.

Includes: add_item, delete_item, update_item, bulk_add_items, prune_table
"""

import logging
from typing import Any

from botocore.exceptions import ClientError
from mcp.server.fastmcp import Context
from mcp.server.session import ServerSession
from mcp.types import ToolAnnotations

from dynamodb_mcp_server.models import (
    AddItemInput,
    BulkAddItemsInput,
    DeleteItemInput,
    PruneTableInput,
    UpdateItemInput,
)
from dynamodb_mcp_server.server import AppContext, mcp
from dynamodb_mcp_server.utils import handle_client_error, to_json

logger = logging.getLogger(__name__)


@mcp.tool(
    name="add_item",
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def add_item(
    input: AddItemInput,
    ctx: Context[ServerSession, AppContext],
) -> str:
    """Add (put) a single item to a DynamoDB table.

    Creates a new item or replaces an existing item with the same primary key.
    Use condition_expression='attribute_not_exists(PK)' to prevent overwrites.

    When to use:
    - To create a new item in a table
    - To replace an entire existing item

    When NOT to use:
    - To update specific attributes (use update_item instead)
    - To add many items at once (use bulk_add_items instead)

    Returns:
        JSON confirmation with the item's primary key.
    """
    app_ctx = ctx.request_context.lifespan_context

    params: dict[str, Any] = {"Item": input.item}
    if input.condition_expression:
        params["ConditionExpression"] = input.condition_expression

    try:
        async with app_ctx.session.resource(
            "dynamodb", endpoint_url=app_ctx.endpoint_url
        ) as resource:
            table = await resource.Table(input.table_name)
            await table.put_item(**params)
    except ClientError as e:
        return handle_client_error(e, "add_item", input.table_name)

    return to_json(
        {
            "message": f"Item added to table '{input.table_name}'.",
            "item_keys": {k: v for k, v in input.item.items() if k in _get_key_names(input.item)},
        }
    )


@mcp.tool(
    name="delete_item",
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def delete_item(
    input: DeleteItemInput,
    ctx: Context[ServerSession, AppContext],
) -> str:
    """Delete a single item from a DynamoDB table by its primary key.

    The item is permanently removed. Use condition_expression to ensure
    the item exists before deleting.

    When to use:
    - To remove a specific item from a table
    - When you know the item's full primary key

    When NOT to use:
    - To delete all items (use prune_table instead)
    - To delete by non-key attributes (scan first, then delete)

    Returns:
        JSON confirmation with the deleted item's key.
    """
    app_ctx = ctx.request_context.lifespan_context

    params: dict[str, Any] = {"Key": input.key}
    if input.condition_expression:
        params["ConditionExpression"] = input.condition_expression

    try:
        async with app_ctx.session.resource(
            "dynamodb", endpoint_url=app_ctx.endpoint_url
        ) as resource:
            table = await resource.Table(input.table_name)
            await table.delete_item(**params)
    except ClientError as e:
        return handle_client_error(e, "delete_item", input.table_name)

    return to_json(
        {
            "message": f"Item deleted from table '{input.table_name}'.",
            "deleted_key": input.key,
        }
    )


@mcp.tool(
    name="update_item",
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def update_item(
    input: UpdateItemInput,
    ctx: Context[ServerSession, AppContext],
) -> str:
    """Update specific attributes of an item in a DynamoDB table.

    Modifies only the specified attributes without replacing the entire item.
    Supports SET, REMOVE, ADD, and DELETE operations in the update expression.
    Returns the updated item's attributes.

    When to use:
    - To modify specific attributes of an existing item
    - To increment counters (SET count = count + :inc)
    - To add/remove elements from sets
    - To remove attributes from an item

    When NOT to use:
    - To replace an entire item (use add_item instead)
    - To update many items at once (iterate with update_item or use bulk operations)

    Returns:
        JSON with the updated item attributes.
    """
    app_ctx = ctx.request_context.lifespan_context

    params: dict[str, Any] = {
        "Key": input.key,
        "UpdateExpression": input.update_expression,
        "ExpressionAttributeValues": input.expression_attribute_values,
        "ReturnValues": "ALL_NEW",
    }
    if input.expression_attribute_names:
        params["ExpressionAttributeNames"] = input.expression_attribute_names
    if input.condition_expression:
        params["ConditionExpression"] = input.condition_expression

    try:
        async with app_ctx.session.resource(
            "dynamodb", endpoint_url=app_ctx.endpoint_url
        ) as resource:
            table = await resource.Table(input.table_name)
            response = await table.update_item(**params)
    except ClientError as e:
        return handle_client_error(e, "update_item", input.table_name)

    return to_json(
        {
            "message": f"Item updated in table '{input.table_name}'.",
            "updated_item": response.get("Attributes", {}),
        }
    )


@mcp.tool(
    name="bulk_add_items",
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def bulk_add_items(
    input: BulkAddItemsInput,
    ctx: Context[ServerSession, AppContext],
) -> str:
    """Add multiple items to a DynamoDB table in efficient batches.

    Uses batch_writer which automatically handles batching (25 items per batch),
    retries on unprocessed items, and flushing. Items with the same primary key
    will overwrite existing items.

    When to use:
    - To add many items at once (more efficient than repeated add_item calls)
    - For data loading or migration scenarios

    When NOT to use:
    - For a single item (use add_item instead)
    - When you need conditional writes (batch_writer doesn't support conditions)

    Returns:
        JSON confirmation with the count of items added.
    """
    app_ctx = ctx.request_context.lifespan_context

    try:
        async with app_ctx.session.resource(
            "dynamodb", endpoint_url=app_ctx.endpoint_url
        ) as resource:
            table = await resource.Table(input.table_name)
            async with table.batch_writer() as batch:
                for item in input.items:
                    await batch.put_item(Item=item)
    except ClientError as e:
        return handle_client_error(e, "bulk_add_items", input.table_name)

    return to_json(
        {
            "message": (
                f"Successfully added {len(input.items)} items to table '{input.table_name}'."
            ),
            "items_added": len(input.items),
        }
    )


@mcp.tool(
    name="prune_table",
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=True,
    ),
)
async def prune_table(
    input: PruneTableInput,
    ctx: Context[ServerSession, AppContext],
) -> str:
    """Delete all items (or filtered items) from a DynamoDB table.

    Scans the table and batch-deletes all matching items. The table itself
    is preserved — only items are removed. Requires confirm=true.

    WARNING: This is a destructive operation. Without a filter_expression,
    ALL items in the table will be permanently deleted.

    When to use:
    - To clear all data from a table while keeping the table structure
    - To delete items matching specific criteria (with filter_expression)
    - For test data cleanup

    When NOT to use:
    - To delete the table itself (not supported by this server)
    - To delete a single item (use delete_item instead)

    Returns:
        JSON with the count of items deleted.
    """
    if not input.confirm:
        return to_json(
            {
                "error": "Destructive operation not confirmed. Set 'confirm' to true to proceed.",
                "hint": (
                    "This will delete ALL items matching the filter (or ALL items if no filter)."
                ),
            }
        )

    app_ctx = ctx.request_context.lifespan_context

    # Get the table's key schema to know which attributes form the primary key
    try:
        async with app_ctx.session.client("dynamodb", endpoint_url=app_ctx.endpoint_url) as client:
            desc_response = await client.describe_table(TableName=input.table_name)
    except ClientError as e:
        return handle_client_error(e, "prune_table (describe)", input.table_name)

    key_schema = desc_response["Table"]["KeySchema"]
    key_names = [k["AttributeName"] for k in key_schema]

    # Scan and delete in batches
    deleted_count = 0
    try:
        async with app_ctx.session.resource(
            "dynamodb", endpoint_url=app_ctx.endpoint_url
        ) as resource:
            table = await resource.Table(input.table_name)

            scan_params: dict[str, Any] = {}
            if input.filter_expression:
                scan_params["FilterExpression"] = input.filter_expression
            if input.expression_attribute_values:
                scan_params["ExpressionAttributeValues"] = input.expression_attribute_values
            if input.expression_attribute_names:
                scan_params["ExpressionAttributeNames"] = input.expression_attribute_names

            # Paginate through all items
            last_key: dict[str, Any] | None = None
            while True:
                if last_key:
                    scan_params["ExclusiveStartKey"] = last_key

                response = await table.scan(**scan_params)
                items = response.get("Items", [])

                if items:
                    async with table.batch_writer() as batch:
                        for item in items:
                            key = {k: item[k] for k in key_names}
                            await batch.delete_item(Key=key)
                    deleted_count += len(items)

                last_key = response.get("LastEvaluatedKey")
                if not last_key:
                    break

    except ClientError as e:
        if deleted_count > 0:
            return to_json(
                {
                    "error": (
                        f"Prune partially completed. Deleted {deleted_count} items before error."
                    ),
                    "details": handle_client_error(e, "prune_table", input.table_name),
                }
            )
        return handle_client_error(e, "prune_table", input.table_name)

    return to_json(
        {
            "message": f"Pruned {deleted_count} items from table '{input.table_name}'.",
            "items_deleted": deleted_count,
            "filter_applied": input.filter_expression is not None,
        }
    )


def _get_key_names(item: dict[str, Any]) -> set[str]:
    """Heuristic to identify likely key attribute names from an item.

    Returns common DynamoDB key naming patterns found in the item.
    Falls back to returning first two keys if no patterns match.
    """
    common_key_names = {"PK", "SK", "pk", "sk", "id", "ID", "key", "sort_key", "partition_key"}
    found = {k for k in item if k in common_key_names}
    if found:
        return found
    keys = list(item.keys())
    return set(keys[:2]) if len(keys) >= 2 else set(keys)
