"""Tests for query and scan tools: query_table, scan_table."""

import json

from dynamodb_mcp_server.models import QueryTableInput, ResponseFormat, ScanTableInput
from dynamodb_mcp_server.tools.query_scan import query_table, scan_table
from tests.conftest import FakeContext


class TestQueryTable:
    async def test_query_by_partition_key(self, ctx: FakeContext, populated_table: str) -> None:
        query_input = QueryTableInput(
            table_name=populated_table,
            key_condition_expression="PK = :pk",
            expression_attribute_values={":pk": "USER#1"},
        )
        result = await query_table(query_input, ctx)
        data = json.loads(result)
        assert data["count"] == 3
        assert len(data["items"]) == 3

    async def test_query_with_sort_key_condition(
        self, ctx: FakeContext, populated_table: str
    ) -> None:
        query_input = QueryTableInput(
            table_name=populated_table,
            key_condition_expression="PK = :pk AND begins_with(SK, :prefix)",
            expression_attribute_values={":pk": "USER#1", ":prefix": "ORDER#"},
        )
        result = await query_table(query_input, ctx)
        data = json.loads(result)
        assert data["count"] == 2
        for item in data["items"]:
            assert item["SK"].startswith("ORDER#")

    async def test_query_with_filter(self, ctx: FakeContext, populated_table: str) -> None:
        query_input = QueryTableInput(
            table_name=populated_table,
            key_condition_expression="PK = :pk AND begins_with(SK, :prefix)",
            expression_attribute_values={
                ":pk": "USER#1",
                ":prefix": "ORDER#",
                ":status": "shipped",
            },
            filter_expression="#s = :status",
            expression_attribute_names={"#s": "status"},
        )
        result = await query_table(query_input, ctx)
        data = json.loads(result)
        assert data["count"] == 1
        assert data["items"][0]["status"] == "shipped"

    async def test_query_with_limit(self, ctx: FakeContext, populated_table: str) -> None:
        query_input = QueryTableInput(
            table_name=populated_table,
            key_condition_expression="PK = :pk",
            expression_attribute_values={":pk": "USER#1"},
            limit=1,
        )
        result = await query_table(query_input, ctx)
        data = json.loads(result)
        assert data["count"] == 1
        assert data["has_more"] is True
        assert "last_evaluated_key" in data

    async def test_query_descending(self, ctx: FakeContext, populated_table: str) -> None:
        query_input = QueryTableInput(
            table_name=populated_table,
            key_condition_expression="PK = :pk AND begins_with(SK, :prefix)",
            expression_attribute_values={":pk": "USER#1", ":prefix": "ORDER#"},
            scan_index_forward=False,
        )
        result = await query_table(query_input, ctx)
        data = json.loads(result)
        assert data["items"][0]["SK"] == "ORDER#002"
        assert data["items"][1]["SK"] == "ORDER#001"

    async def test_query_markdown_format(self, ctx: FakeContext, populated_table: str) -> None:
        query_input = QueryTableInput(
            table_name=populated_table,
            key_condition_expression="PK = :pk AND SK = :sk",
            expression_attribute_values={":pk": "USER#1", ":sk": "PROFILE"},
            format=ResponseFormat.MARKDOWN,
        )
        result = await query_table(query_input, ctx)
        assert "**Results:**" in result
        assert "Alice" in result
        assert "|" in result

    async def test_query_nonexistent_table(self, ctx: FakeContext) -> None:
        query_input = QueryTableInput(
            table_name="nonexistent",
            key_condition_expression="PK = :pk",
            expression_attribute_values={":pk": "test"},
        )
        result = await query_table(query_input, ctx)
        assert "Error" in result

    async def test_query_no_results(self, ctx: FakeContext, populated_table: str) -> None:
        query_input = QueryTableInput(
            table_name=populated_table,
            key_condition_expression="PK = :pk",
            expression_attribute_values={":pk": "NONEXISTENT"},
        )
        result = await query_table(query_input, ctx)
        data = json.loads(result)
        assert data["count"] == 0
        assert data["items"] == []
        assert data["has_more"] is False


class TestScanTable:
    async def test_scan_all_items(self, ctx: FakeContext, populated_table: str) -> None:
        scan_input = ScanTableInput(table_name=populated_table)
        result = await scan_table(scan_input, ctx)
        data = json.loads(result)
        assert data["count"] == 5

    async def test_scan_with_filter(self, ctx: FakeContext, populated_table: str) -> None:
        scan_input = ScanTableInput(
            table_name=populated_table,
            filter_expression="#s = :status",
            expression_attribute_values={":status": "shipped"},
            expression_attribute_names={"#s": "status"},
        )
        result = await scan_table(scan_input, ctx)
        data = json.loads(result)
        assert data["count"] == 2
        for item in data["items"]:
            assert item["status"] == "shipped"

    async def test_scan_with_limit(self, ctx: FakeContext, populated_table: str) -> None:
        scan_input = ScanTableInput(table_name=populated_table, limit=2)
        result = await scan_table(scan_input, ctx)
        data = json.loads(result)
        assert data["count"] == 2
        assert data["has_more"] is True

    async def test_scan_empty_table(self, ctx: FakeContext, composite_table: str) -> None:
        scan_input = ScanTableInput(table_name=composite_table)
        result = await scan_table(scan_input, ctx)
        data = json.loads(result)
        assert data["count"] == 0
        assert data["items"] == []

    async def test_scan_markdown_format(self, ctx: FakeContext, populated_table: str) -> None:
        scan_input = ScanTableInput(
            table_name=populated_table,
            format=ResponseFormat.MARKDOWN,
            limit=5,
        )
        result = await scan_table(scan_input, ctx)
        assert "**Results:**" in result
        assert "|" in result

    async def test_scan_nonexistent_table(self, ctx: FakeContext) -> None:
        scan_input = ScanTableInput(table_name="nonexistent")
        result = await scan_table(scan_input, ctx)
        assert "Error" in result

    async def test_scan_pagination(self, ctx: FakeContext, populated_table: str) -> None:
        first_scan = ScanTableInput(table_name=populated_table, limit=2)
        result1 = await scan_table(first_scan, ctx)
        data1 = json.loads(result1)
        assert data1["has_more"] is True

        second_scan = ScanTableInput(
            table_name=populated_table,
            limit=10,
            exclusive_start_key=data1["last_evaluated_key"],
        )
        result2 = await scan_table(second_scan, ctx)
        data2 = json.loads(result2)
        assert data2["count"] == 3
