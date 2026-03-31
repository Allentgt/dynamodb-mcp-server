"""Shared utility functions for the DynamoDB MCP server.

Provides error handling, response formatting, pagination helpers,
and truncation logic used across all tool modules.
"""

import json
import logging
from decimal import Decimal
from typing import Any

from botocore.exceptions import ClientError

from dynamodb_mcp_server.models import ResponseFormat

logger = logging.getLogger(__name__)

CHARACTER_LIMIT = 25_000
DEFAULT_PAGE_SIZE = 25


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that handles DynamoDB Decimal types and non-serializable objects."""

    def default(self, o: object) -> Any:
        if isinstance(o, Decimal):
            if o == int(o):
                return int(o)
            return float(o)
        try:
            return super().default(o)
        except TypeError:
            return str(o)


def to_json(data: Any) -> str:
    """Serialize data to JSON string, handling DynamoDB Decimal types."""
    return json.dumps(data, cls=DecimalEncoder, indent=2)


def handle_client_error(e: ClientError, operation: str, table_name: str | None = None) -> str:
    """Convert a botocore ClientError into an actionable error message for agents.

    Returns a human-readable string describing the error and suggesting next steps.
    """
    error_code = e.response["Error"]["Code"]
    error_message = e.response["Error"]["Message"]
    context = f" on table '{table_name}'" if table_name else ""

    logger.error("%s failed%s: %s — %s", operation, context, error_code, error_message)

    error_map: dict[str, str] = {
        "ResourceNotFoundException": (
            f"Error: Table '{table_name}' not found. Use list_tables to see available tables."
        ),
        "ConditionalCheckFailedException": (
            f"Error: Condition check failed for {operation}{context}. "
            "The condition_expression evaluated to false. "
            "Verify the item exists and meets the specified conditions."
        ),
        "ValidationException": (
            f"Error: Invalid request for {operation}{context}: {error_message}. "
            "Check expression syntax and attribute names/values."
        ),
        "ProvisionedThroughputExceededException": (
            f"Error: Throughput exceeded{context}. "
            "Retry after a brief delay or reduce request rate."
        ),
        "ResourceInUseException": (
            f"Error: Table '{table_name}' is being updated. "
            "Wait for the current operation to complete before retrying."
        ),
        "LimitExceededException": (
            f"Error: AWS service limit exceeded for {operation}{context}. "
            "Check your account limits or reduce concurrent operations."
        ),
        "ItemCollectionSizeLimitExceededException": (
            f"Error: Item collection too large{context}. "
            "The item collection (all items sharing same partition key) exceeds 10 GB."
        ),
    }

    return error_map.get(
        error_code, f"Error: {operation}{context} failed — {error_code}: {error_message}"
    )


def truncate_response(content: str, limit: int = CHARACTER_LIMIT) -> str:
    """Truncate response content if it exceeds the character limit.

    Appends a truncation notice suggesting the agent use filters or pagination.
    """
    if len(content) <= limit:
        return content

    truncated = content[:limit]
    notice = (
        "\n\n--- RESPONSE TRUNCATED ---\n"
        f"Response exceeded {limit:,} character limit. "
        "Use 'limit' parameter to reduce results, add filter expressions, "
        "or paginate with 'exclusive_start_key'."
    )
    return truncated + notice


def format_items_as_markdown(items: list[dict[str, Any]]) -> str:
    """Format a list of DynamoDB items as a Markdown table.

    Handles varying columns across items by collecting all unique keys.
    """
    if not items:
        return "_No items found._"

    all_keys: list[str] = []
    seen: set[str] = set()
    for item in items:
        for key in item:
            if key not in seen:
                all_keys.append(key)
                seen.add(key)

    header = "| " + " | ".join(all_keys) + " |"
    separator = "| " + " | ".join("---" for _ in all_keys) + " |"

    rows: list[str] = []
    for item in items:
        cells = []
        for key in all_keys:
            value = item.get(key, "")
            cell = str(value).replace("|", "\\|").replace("\n", " ")
            if len(cell) > 100:
                cell = cell[:97] + "..."
            cells.append(cell)
        rows.append("| " + " | ".join(cells) + " |")

    return "\n".join([header, separator, *rows])


def build_query_response(
    items: list[dict[str, Any]],
    count: int,
    scanned_count: int,
    last_evaluated_key: dict[str, Any] | None,
    fmt: ResponseFormat,
) -> str:
    """Build a formatted response for query/scan operations."""
    result: dict[str, Any] = {
        "count": count,
        "scanned_count": scanned_count,
        "has_more": last_evaluated_key is not None,
    }

    if last_evaluated_key:
        result["last_evaluated_key"] = last_evaluated_key

    if fmt == ResponseFormat.MARKDOWN:
        parts = [
            f"**Results:** {count} items returned ({scanned_count} scanned)",
        ]
        if last_evaluated_key:
            parts.append(f"**Next page key:** `{to_json(last_evaluated_key)}`")
        parts.append("")
        parts.append(format_items_as_markdown(items))
        content = "\n".join(parts)
    else:
        result["items"] = items
        content = to_json(result)

    return truncate_response(content)
