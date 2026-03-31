"""Pydantic input models for all DynamoDB MCP tools.

Each model validates and documents the parameters for a single MCP tool.
Field descriptions become the tool parameter documentation visible to agents.
"""

from enum import StrEnum

from pydantic import BaseModel, Field


class ResponseFormat(StrEnum):
    """Output format for tool responses."""

    JSON = "json"
    MARKDOWN = "markdown"


class ListTablesInput(BaseModel):
    """Input for list_tables tool."""

    exclusive_start_table_name: str | None = Field(
        default=None,
        description="Table name to start listing from (for pagination). "
        "Use the value returned in 'next_table_name' from a previous call.",
    )
    limit: int = Field(
        default=100,
        ge=1,
        le=100,
        description="Maximum number of table names to return (1-100).",
    )


class DescribeTableInput(BaseModel):
    """Input for describe_table tool."""

    table_name: str = Field(
        min_length=1,
        max_length=255,
        description="Name of the DynamoDB table to describe.",
    )


class CreateGsiInput(BaseModel):
    """Input for create_gsi tool."""

    table_name: str = Field(
        min_length=1,
        max_length=255,
        description="Name of the table to add the GSI to.",
    )
    index_name: str = Field(
        min_length=1,
        max_length=255,
        description="Name for the new Global Secondary Index.",
    )
    partition_key: str = Field(
        min_length=1,
        description="Attribute name to use as the GSI partition key.",
    )
    partition_key_type: str = Field(
        default="S",
        description="DynamoDB type for the partition key: S (string), N (number), or B (binary).",
    )
    sort_key: str | None = Field(
        default=None,
        description="Optional attribute name for the GSI sort key.",
    )
    sort_key_type: str = Field(
        default="S",
        description="DynamoDB type for the sort key: S (string), N (number), or B (binary). "
        "Only used if sort_key is provided.",
    )
    projection_type: str = Field(
        default="ALL",
        description="Attributes to project into the index: ALL, KEYS_ONLY, or INCLUDE.",
    )
    non_key_attributes: list[str] | None = Field(
        default=None,
        description="List of attribute names to project when projection_type is INCLUDE.",
    )


class CreateTableInput(BaseModel):
    """Input for create_table tool."""

    table_name: str = Field(
        min_length=3,
        max_length=255,
        description="Name for the new DynamoDB table (3-255 characters).",
    )
    partition_key: str = Field(
        min_length=1,
        description="Attribute name for the partition (hash) key.",
    )
    partition_key_type: str = Field(
        default="S",
        description="DynamoDB type for the partition key: S (string), N (number), or B (binary).",
    )
    sort_key: str | None = Field(
        default=None,
        description="Optional attribute name for the sort (range) key.",
    )
    sort_key_type: str = Field(
        default="S",
        description="DynamoDB type for the sort key: S (string), N (number), or B (binary). "
        "Only used if sort_key is provided.",
    )
    billing_mode: str = Field(
        default="PAY_PER_REQUEST",
        description="Billing mode: PAY_PER_REQUEST (on-demand, default) "
        "or PROVISIONED (requires read/write capacity units).",
    )
    read_capacity_units: int | None = Field(
        default=None,
        ge=1,
        description="Provisioned read capacity units. Required when billing_mode is PROVISIONED.",
    )
    write_capacity_units: int | None = Field(
        default=None,
        ge=1,
        description="Provisioned write capacity units. Required when billing_mode is PROVISIONED.",
    )
    tags: dict[str, str] | None = Field(
        default=None,
        description="Optional tags to apply to the table, e.g. {'Environment': 'production'}.",
    )


class QueryTableInput(BaseModel):
    """Input for query_table tool."""

    table_name: str = Field(
        min_length=1,
        max_length=255,
        description="Name of the DynamoDB table to query.",
    )
    key_condition_expression: str = Field(
        min_length=1,
        description="Key condition expression, e.g. 'PK = :pk AND SK begins_with :prefix'. "
        "Must reference the table's partition key and optionally the sort key.",
    )
    expression_attribute_values: dict[str, str | int | float | bool] = Field(
        description="Map of expression attribute value placeholders to their values, "
        "e.g. {':pk': 'USER#123', ':prefix': 'ORDER#'}.",
    )
    filter_expression: str | None = Field(
        default=None,
        description="Optional filter expression applied after the query, "
        "e.g. 'status = :status'. Does not reduce read capacity consumed.",
    )
    expression_attribute_names: dict[str, str] | None = Field(
        default=None,
        description="Map of expression attribute name placeholders, "
        "e.g. {'#s': 'status'} for reserved words.",
    )
    index_name: str | None = Field(
        default=None,
        description="Name of a GSI or LSI to query instead of the base table.",
    )
    limit: int = Field(
        default=25,
        ge=1,
        le=1000,
        description="Maximum number of items to return (1-1000).",
    )
    scan_index_forward: bool = Field(
        default=True,
        description="True for ascending sort key order, False for descending.",
    )
    exclusive_start_key: dict[str, str | int | float | bool] | None = Field(
        default=None,
        description="Primary key of the item to start reading after (for pagination). "
        "Use the 'last_evaluated_key' from a previous response.",
    )
    format: ResponseFormat = Field(
        default=ResponseFormat.JSON,
        description="Response format: 'json' for structured data, 'markdown' for readable table.",
    )


class ScanTableInput(BaseModel):
    """Input for scan_table tool."""

    table_name: str = Field(
        min_length=1,
        max_length=255,
        description="Name of the DynamoDB table to scan.",
    )
    filter_expression: str | None = Field(
        default=None,
        description="Optional filter expression, e.g. 'age > :min_age AND active = :active'. "
        "Applied after reading; does not reduce read capacity consumed.",
    )
    expression_attribute_values: dict[str, str | int | float | bool] | None = Field(
        default=None,
        description="Map of expression attribute value placeholders to values, "
        "required if filter_expression uses placeholders.",
    )
    expression_attribute_names: dict[str, str] | None = Field(
        default=None,
        description="Map of expression attribute name placeholders for reserved words.",
    )
    index_name: str | None = Field(
        default=None,
        description="Name of a GSI or LSI to scan instead of the base table.",
    )
    limit: int = Field(
        default=25,
        ge=1,
        le=1000,
        description="Maximum number of items to return (1-1000).",
    )
    exclusive_start_key: dict[str, str | int | float | bool] | None = Field(
        default=None,
        description="Primary key to start scanning after (for pagination). "
        "Use the 'last_evaluated_key' from a previous response.",
    )
    format: ResponseFormat = Field(
        default=ResponseFormat.JSON,
        description="Response format: 'json' for structured data, 'markdown' for readable table.",
    )


class AddItemInput(BaseModel):
    """Input for add_item tool."""

    table_name: str = Field(
        min_length=1,
        max_length=255,
        description="Name of the DynamoDB table to add the item to.",
    )
    item: dict[str, str | int | float | bool | None | list | dict] = Field(
        description="The item to add. Must include the table's partition key "
        "(and sort key if the table has one). "
        "Example: {'PK': 'USER#123', 'SK': 'PROFILE', 'name': 'Alice', 'age': 30}.",
    )
    condition_expression: str | None = Field(
        default=None,
        description="Optional condition that must be met for the put to succeed, "
        "e.g. 'attribute_not_exists(PK)' to prevent overwrites.",
    )


class DeleteItemInput(BaseModel):
    """Input for delete_item tool."""

    table_name: str = Field(
        min_length=1,
        max_length=255,
        description="Name of the DynamoDB table to delete the item from.",
    )
    key: dict[str, str | int | float | bool] = Field(
        description="Primary key of the item to delete. Must include partition key "
        "(and sort key if the table has one). Example: {'PK': 'USER#123', 'SK': 'PROFILE'}.",
    )
    condition_expression: str | None = Field(
        default=None,
        description="Optional condition that must be met for deletion, "
        "e.g. 'attribute_exists(PK)' to only delete if the item exists.",
    )


class UpdateItemInput(BaseModel):
    """Input for update_item tool."""

    table_name: str = Field(
        min_length=1,
        max_length=255,
        description="Name of the DynamoDB table containing the item to update.",
    )
    key: dict[str, str | int | float | bool] = Field(
        description="Primary key of the item to update. "
        "Example: {'PK': 'USER#123', 'SK': 'PROFILE'}.",
    )
    update_expression: str = Field(
        min_length=1,
        description="Update expression defining the changes, "
        "e.g. 'SET #n = :name, age = :age REMOVE old_field'.",
    )
    expression_attribute_values: dict[str, str | int | float | bool | None | list | dict] = Field(
        description="Map of expression value placeholders, e.g. {':name': 'Bob', ':age': 31}.",
    )
    expression_attribute_names: dict[str, str] | None = Field(
        default=None,
        description="Map of expression name placeholders for reserved words, "
        "e.g. {'#n': 'name', '#s': 'status'}.",
    )
    condition_expression: str | None = Field(
        default=None,
        description="Optional condition that must be true for the update to proceed, "
        "e.g. 'attribute_exists(PK)' to only update existing items.",
    )


class BulkAddItemsInput(BaseModel):
    """Input for bulk_add_items tool."""

    table_name: str = Field(
        min_length=1,
        max_length=255,
        description="Name of the DynamoDB table to add items to.",
    )
    items: list[dict[str, str | int | float | bool | None | list | dict]] = Field(
        min_length=1,
        max_length=500,
        description="List of items to add (1-500). Each item must include the table's "
        "primary key attributes. Items are written in batches of 25 automatically.",
    )


class PruneTableInput(BaseModel):
    """Input for prune_table tool."""

    table_name: str = Field(
        min_length=1,
        max_length=255,
        description="Name of the DynamoDB table to prune (delete all items from).",
    )
    confirm: bool = Field(
        description="Must be set to true to confirm the destructive operation. "
        "This will delete ALL items in the table.",
    )
    filter_expression: str | None = Field(
        default=None,
        description="Optional filter to only delete matching items, "
        "e.g. 'created_at < :cutoff'. If omitted, ALL items are deleted.",
    )
    expression_attribute_values: dict[str, str | int | float | bool] | None = Field(
        default=None,
        description="Expression value placeholders for the filter_expression.",
    )
    expression_attribute_names: dict[str, str] | None = Field(
        default=None,
        description="Expression name placeholders for reserved words in filter_expression.",
    )
