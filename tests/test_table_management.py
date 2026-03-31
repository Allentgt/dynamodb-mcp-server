"""Tests for table management tools: list_tables, describe_table, create_gsi."""

import json
from typing import Any

from dynamodb_mcp_server.models import CreateGsiInput, DescribeTableInput, ListTablesInput
from dynamodb_mcp_server.tools.table_management import create_gsi, describe_table, list_tables
from tests.conftest import FakeContext


class TestListTables:
    async def test_returns_table_names(self, ctx: FakeContext, simple_table: str) -> None:
        result = await list_tables(ListTablesInput(), ctx)
        data = json.loads(result)
        assert simple_table in data["table_names"]
        assert data["count"] >= 1
        assert data["has_more"] is False

    async def test_empty_account(self, ctx: FakeContext) -> None:
        result = await list_tables(ListTablesInput(), ctx)
        data = json.loads(result)
        assert data["table_names"] == []
        assert data["count"] == 0

    async def test_pagination_with_limit(self, ctx: FakeContext, dynamodb_resource: Any) -> None:
        for i in range(3):
            dynamodb_resource.create_table(
                TableName=f"table-{i}",
                KeySchema=[{"AttributeName": "PK", "KeyType": "HASH"}],
                AttributeDefinitions=[{"AttributeName": "PK", "AttributeType": "S"}],
                BillingMode="PAY_PER_REQUEST",
            )

        result = await list_tables(ListTablesInput(limit=2), ctx)
        data = json.loads(result)
        assert data["count"] == 2
        assert data["has_more"] is True
        assert "next_table_name" in data

    async def test_multiple_tables(
        self, ctx: FakeContext, simple_table: str, composite_table: str
    ) -> None:
        result = await list_tables(ListTablesInput(), ctx)
        data = json.loads(result)
        assert simple_table in data["table_names"]
        assert composite_table in data["table_names"]


class TestDescribeTable:
    async def test_describes_simple_table(self, ctx: FakeContext, simple_table: str) -> None:
        result = await describe_table(DescribeTableInput(table_name=simple_table), ctx)
        data = json.loads(result)
        assert data["table_name"] == simple_table
        assert data["status"] == "ACTIVE"
        assert len(data["key_schema"]) == 1
        assert data["key_schema"][0]["AttributeName"] == "PK"

    async def test_describes_composite_table(self, ctx: FakeContext, composite_table: str) -> None:
        result = await describe_table(DescribeTableInput(table_name=composite_table), ctx)
        data = json.loads(result)
        assert len(data["key_schema"]) == 2
        key_names = {k["AttributeName"] for k in data["key_schema"]}
        assert key_names == {"PK", "SK"}

    async def test_nonexistent_table_error(self, ctx: FakeContext) -> None:
        result = await describe_table(DescribeTableInput(table_name="nonexistent"), ctx)
        assert "Error" in result
        assert "not found" in result
        assert "list_tables" in result

    async def test_includes_item_count(self, ctx: FakeContext, simple_table: str) -> None:
        result = await describe_table(DescribeTableInput(table_name=simple_table), ctx)
        data = json.loads(result)
        assert "item_count" in data
        assert "table_size_bytes" in data


class TestCreateGsi:
    async def test_creates_gsi_hash_only(self, ctx: FakeContext, simple_table: str) -> None:
        gsi_input = CreateGsiInput(
            table_name=simple_table,
            index_name="email-index",
            partition_key="email",
            partition_key_type="S",
        )
        result = await create_gsi(gsi_input, ctx)
        data = json.loads(result)
        assert data["index_name"] == "email-index"
        assert data["status"] == "CREATING"
        assert "next_step" in data

    async def test_creates_gsi_with_sort_key(self, ctx: FakeContext, simple_table: str) -> None:
        gsi_input = CreateGsiInput(
            table_name=simple_table,
            index_name="status-date-index",
            partition_key="status",
            partition_key_type="S",
            sort_key="created_at",
            sort_key_type="S",
        )
        result = await create_gsi(gsi_input, ctx)
        data = json.loads(result)
        assert data["index_name"] == "status-date-index"
        assert len(data["key_schema"]) == 2

    async def test_creates_gsi_keys_only_projection(
        self, ctx: FakeContext, simple_table: str
    ) -> None:
        gsi_input = CreateGsiInput(
            table_name=simple_table,
            index_name="keys-only-index",
            partition_key="type",
            projection_type="KEYS_ONLY",
        )
        result = await create_gsi(gsi_input, ctx)
        data = json.loads(result)
        assert data["projection"]["ProjectionType"] == "KEYS_ONLY"

    async def test_nonexistent_table_error(self, ctx: FakeContext) -> None:
        gsi_input = CreateGsiInput(
            table_name="nonexistent",
            index_name="test-index",
            partition_key="attr",
        )
        result = await create_gsi(gsi_input, ctx)
        assert "Error" in result

    async def test_gsi_visible_in_describe(self, ctx: FakeContext, simple_table: str) -> None:
        gsi_input = CreateGsiInput(
            table_name=simple_table,
            index_name="verify-index",
            partition_key="field",
        )
        await create_gsi(gsi_input, ctx)

        desc_result = await describe_table(DescribeTableInput(table_name=simple_table), ctx)
        desc_data = json.loads(desc_result)
        gsi_names = [g["index_name"] for g in desc_data.get("global_secondary_indexes", [])]
        assert "verify-index" in gsi_names
