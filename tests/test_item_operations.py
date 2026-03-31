"""Tests for item operation tools: add, delete, update, bulk_add, prune."""

import json

from dynamodb_mcp_server.models import (
    AddItemInput,
    BulkAddItemsInput,
    DeleteItemInput,
    PruneTableInput,
    ScanTableInput,
    UpdateItemInput,
)
from dynamodb_mcp_server.tools.item_operations import (
    add_item,
    bulk_add_items,
    delete_item,
    prune_table,
    update_item,
)
from dynamodb_mcp_server.tools.query_scan import scan_table
from tests.conftest import FakeContext


class TestAddItem:
    async def test_add_simple_item(self, ctx: FakeContext, simple_table: str) -> None:
        input_data = AddItemInput(
            table_name=simple_table,
            item={"PK": "item-1", "name": "Test", "value": 42},
        )
        result = await add_item(input_data, ctx)
        data = json.loads(result)
        assert "added" in data["message"].lower()

    async def test_add_item_to_composite_table(
        self, ctx: FakeContext, composite_table: str
    ) -> None:
        input_data = AddItemInput(
            table_name=composite_table,
            item={"PK": "USER#99", "SK": "PROFILE", "name": "Charlie"},
        )
        result = await add_item(input_data, ctx)
        data = json.loads(result)
        assert "added" in data["message"].lower()

    async def test_add_item_nonexistent_table(self, ctx: FakeContext) -> None:
        input_data = AddItemInput(
            table_name="nonexistent",
            item={"PK": "test"},
        )
        result = await add_item(input_data, ctx)
        assert "Error" in result

    async def test_add_item_with_condition_prevents_overwrite(
        self, ctx: FakeContext, simple_table: str
    ) -> None:
        input_data = AddItemInput(
            table_name=simple_table,
            item={"PK": "unique-1", "data": "first"},
        )
        await add_item(input_data, ctx)

        overwrite_input = AddItemInput(
            table_name=simple_table,
            item={"PK": "unique-1", "data": "second"},
            condition_expression="attribute_not_exists(PK)",
        )
        result = await add_item(overwrite_input, ctx)
        assert "Error" in result
        assert "condition" in result.lower() or "Condition" in result

    async def test_add_item_retrievable_via_scan(self, ctx: FakeContext, simple_table: str) -> None:
        input_data = AddItemInput(
            table_name=simple_table,
            item={"PK": "verify-1", "color": "blue"},
        )
        await add_item(input_data, ctx)

        scan_result = await scan_table(ScanTableInput(table_name=simple_table), ctx)
        scan_data = json.loads(scan_result)
        pks = [item["PK"] for item in scan_data["items"]]
        assert "verify-1" in pks


class TestDeleteItem:
    async def test_delete_existing_item(self, ctx: FakeContext, populated_table: str) -> None:
        input_data = DeleteItemInput(
            table_name=populated_table,
            key={"PK": "USER#1", "SK": "PROFILE"},
        )
        result = await delete_item(input_data, ctx)
        data = json.loads(result)
        assert "deleted" in data["message"].lower()
        assert data["deleted_key"]["PK"] == "USER#1"

    async def test_delete_nonexistent_key_succeeds(
        self, ctx: FakeContext, populated_table: str
    ) -> None:
        input_data = DeleteItemInput(
            table_name=populated_table,
            key={"PK": "NOPE", "SK": "NADA"},
        )
        result = await delete_item(input_data, ctx)
        data = json.loads(result)
        assert "deleted" in data["message"].lower()

    async def test_delete_with_condition(self, ctx: FakeContext, populated_table: str) -> None:
        input_data = DeleteItemInput(
            table_name=populated_table,
            key={"PK": "NOPE", "SK": "NADA"},
            condition_expression="attribute_exists(PK)",
        )
        result = await delete_item(input_data, ctx)
        assert "Error" in result

    async def test_delete_from_nonexistent_table(self, ctx: FakeContext) -> None:
        input_data = DeleteItemInput(
            table_name="nonexistent",
            key={"PK": "test"},
        )
        result = await delete_item(input_data, ctx)
        assert "Error" in result

    async def test_delete_removes_item(self, ctx: FakeContext, populated_table: str) -> None:
        await delete_item(
            DeleteItemInput(table_name=populated_table, key={"PK": "USER#2", "SK": "PROFILE"}),
            ctx,
        )

        scan_result = await scan_table(ScanTableInput(table_name=populated_table), ctx)
        scan_data = json.loads(scan_result)
        keys = [(i["PK"], i["SK"]) for i in scan_data["items"]]
        assert ("USER#2", "PROFILE") not in keys


class TestUpdateItem:
    async def test_update_existing_item(self, ctx: FakeContext, populated_table: str) -> None:
        input_data = UpdateItemInput(
            table_name=populated_table,
            key={"PK": "USER#1", "SK": "PROFILE"},
            update_expression="SET #n = :name, age = :age",
            expression_attribute_values={":name": "Alice Updated", ":age": 31},
            expression_attribute_names={"#n": "name"},
        )
        result = await update_item(input_data, ctx)
        data = json.loads(result)
        assert "updated" in data["message"].lower()
        assert data["updated_item"]["name"] == "Alice Updated"
        assert data["updated_item"]["age"] == 31

    async def test_update_creates_new_item(self, ctx: FakeContext, composite_table: str) -> None:
        input_data = UpdateItemInput(
            table_name=composite_table,
            key={"PK": "NEW#1", "SK": "DATA"},
            update_expression="SET val = :v",
            expression_attribute_values={":v": "hello"},
        )
        result = await update_item(input_data, ctx)
        data = json.loads(result)
        assert data["updated_item"]["val"] == "hello"

    async def test_update_with_condition_failure(
        self, ctx: FakeContext, composite_table: str
    ) -> None:
        input_data = UpdateItemInput(
            table_name=composite_table,
            key={"PK": "NOPE", "SK": "NADA"},
            update_expression="SET val = :v",
            expression_attribute_values={":v": "test"},
            condition_expression="attribute_exists(PK)",
        )
        result = await update_item(input_data, ctx)
        assert "Error" in result

    async def test_update_nonexistent_table(self, ctx: FakeContext) -> None:
        input_data = UpdateItemInput(
            table_name="nonexistent",
            key={"PK": "test"},
            update_expression="SET val = :v",
            expression_attribute_values={":v": "test"},
        )
        result = await update_item(input_data, ctx)
        assert "Error" in result


class TestBulkAddItems:
    async def test_bulk_add_multiple_items(self, ctx: FakeContext, simple_table: str) -> None:
        items = [{"PK": f"bulk-{i}", "data": f"value-{i}"} for i in range(10)]
        input_data = BulkAddItemsInput(table_name=simple_table, items=items)
        result = await bulk_add_items(input_data, ctx)
        data = json.loads(result)
        assert data["items_added"] == 10

        scan_result = await scan_table(ScanTableInput(table_name=simple_table, limit=100), ctx)
        scan_data = json.loads(scan_result)
        assert scan_data["count"] == 10

    async def test_bulk_add_single_item(self, ctx: FakeContext, simple_table: str) -> None:
        input_data = BulkAddItemsInput(
            table_name=simple_table,
            items=[{"PK": "single", "val": 1}],
        )
        result = await bulk_add_items(input_data, ctx)
        data = json.loads(result)
        assert data["items_added"] == 1

    async def test_bulk_add_nonexistent_table(self, ctx: FakeContext) -> None:
        input_data = BulkAddItemsInput(
            table_name="nonexistent",
            items=[{"PK": "test"}],
        )
        result = await bulk_add_items(input_data, ctx)
        assert "Error" in result

    async def test_bulk_add_overwrites_existing(self, ctx: FakeContext, simple_table: str) -> None:
        input_data = BulkAddItemsInput(
            table_name=simple_table,
            items=[{"PK": "overwrite-test", "version": 1}],
        )
        await bulk_add_items(input_data, ctx)

        input_data2 = BulkAddItemsInput(
            table_name=simple_table,
            items=[{"PK": "overwrite-test", "version": 2}],
        )
        await bulk_add_items(input_data2, ctx)

        scan_result = await scan_table(ScanTableInput(table_name=simple_table), ctx)
        scan_data = json.loads(scan_result)
        item = next(i for i in scan_data["items"] if i["PK"] == "overwrite-test")
        assert item["version"] == 2


class TestPruneTable:
    async def test_prune_requires_confirm(self, ctx: FakeContext, populated_table: str) -> None:
        input_data = PruneTableInput(
            table_name=populated_table,
            confirm=False,
        )
        result = await prune_table(input_data, ctx)
        data = json.loads(result)
        assert "error" in data
        assert "confirm" in data["error"].lower() or "confirm" in data.get("hint", "").lower()

    async def test_prune_all_items(self, ctx: FakeContext, populated_table: str) -> None:
        input_data = PruneTableInput(
            table_name=populated_table,
            confirm=True,
        )
        result = await prune_table(input_data, ctx)
        data = json.loads(result)
        assert data["items_deleted"] == 5
        assert data["filter_applied"] is False

        scan_result = await scan_table(ScanTableInput(table_name=populated_table), ctx)
        scan_data = json.loads(scan_result)
        assert scan_data["count"] == 0

    async def test_prune_with_filter(self, ctx: FakeContext, populated_table: str) -> None:
        input_data = PruneTableInput(
            table_name=populated_table,
            confirm=True,
            filter_expression="begins_with(SK, :prefix)",
            expression_attribute_values={":prefix": "ORDER#"},
        )
        result = await prune_table(input_data, ctx)
        data = json.loads(result)
        assert data["items_deleted"] == 3
        assert data["filter_applied"] is True

        scan_result = await scan_table(ScanTableInput(table_name=populated_table), ctx)
        scan_data = json.loads(scan_result)
        assert scan_data["count"] == 2
        for item in scan_data["items"]:
            assert item["SK"] == "PROFILE"

    async def test_prune_nonexistent_table(self, ctx: FakeContext) -> None:
        input_data = PruneTableInput(
            table_name="nonexistent",
            confirm=True,
        )
        result = await prune_table(input_data, ctx)
        assert "Error" in result

    async def test_prune_empty_table(self, ctx: FakeContext, composite_table: str) -> None:
        input_data = PruneTableInput(
            table_name=composite_table,
            confirm=True,
        )
        result = await prune_table(input_data, ctx)
        data = json.loads(result)
        assert data["items_deleted"] == 0
