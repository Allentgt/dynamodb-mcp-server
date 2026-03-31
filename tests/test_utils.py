import json
from decimal import Decimal
from typing import Any

from botocore.exceptions import ClientError

from dynamodb_mcp_server.models import ResponseFormat
from dynamodb_mcp_server.utils import (
    CHARACTER_LIMIT,
    build_query_response,
    format_items_as_markdown,
    handle_client_error,
    to_json,
    truncate_response,
)


class TestDecimalEncoder:
    def test_integer_decimal(self) -> None:
        result = to_json({"count": Decimal("42")})
        data = json.loads(result)
        assert data["count"] == 42
        assert isinstance(data["count"], int)

    def test_float_decimal(self) -> None:
        result = to_json({"price": Decimal("9.99")})
        data = json.loads(result)
        assert data["price"] == 9.99

    def test_nested_decimals(self) -> None:
        result = to_json({"items": [{"val": Decimal("1")}, {"val": Decimal("2.5")}]})
        data = json.loads(result)
        assert data["items"][0]["val"] == 1
        assert data["items"][1]["val"] == 2.5


class TestHandleClientError:
    def _make_error(self, code: str, message: str = "test message") -> ClientError:
        return ClientError(
            error_response={"Error": {"Code": code, "Message": message}},
            operation_name="TestOp",
        )

    def test_resource_not_found(self) -> None:
        err = self._make_error("ResourceNotFoundException")
        result = handle_client_error(err, "describe_table", "my-table")
        assert "not found" in result
        assert "my-table" in result
        assert "list_tables" in result

    def test_conditional_check_failed(self) -> None:
        err = self._make_error("ConditionalCheckFailedException")
        result = handle_client_error(err, "add_item", "my-table")
        assert "condition" in result.lower()

    def test_validation_exception(self) -> None:
        err = self._make_error("ValidationException", "Invalid expression")
        result = handle_client_error(err, "query", "tbl")
        assert "Invalid expression" in result

    def test_throughput_exceeded(self) -> None:
        err = self._make_error("ProvisionedThroughputExceededException")
        result = handle_client_error(err, "scan", "tbl")
        assert "Throughput" in result or "throughput" in result

    def test_unknown_error_includes_code(self) -> None:
        err = self._make_error("SomeNewError", "details here")
        result = handle_client_error(err, "op", "tbl")
        assert "SomeNewError" in result
        assert "details here" in result

    def test_no_table_name(self) -> None:
        err = self._make_error("ResourceNotFoundException")
        result = handle_client_error(err, "list_tables")
        assert "Error" in result


class TestTruncateResponse:
    def test_short_content_unchanged(self) -> None:
        content = "short"
        assert truncate_response(content) == content

    def test_long_content_truncated(self) -> None:
        content = "x" * (CHARACTER_LIMIT + 1000)
        result = truncate_response(content)
        assert "TRUNCATED" in result
        assert len(result) < len(content)

    def test_custom_limit(self) -> None:
        content = "a" * 200
        result = truncate_response(content, limit=100)
        assert "TRUNCATED" in result

    def test_exact_limit_not_truncated(self) -> None:
        content = "a" * CHARACTER_LIMIT
        result = truncate_response(content)
        assert "TRUNCATED" not in result


class TestFormatItemsAsMarkdown:
    def test_empty_items(self) -> None:
        result = format_items_as_markdown([])
        assert "No items" in result

    def test_single_item(self) -> None:
        items: list[dict[str, Any]] = [{"PK": "test", "name": "Alice"}]
        result = format_items_as_markdown(items)
        assert "PK" in result
        assert "name" in result
        assert "Alice" in result
        assert "|" in result

    def test_heterogeneous_items(self) -> None:
        items: list[dict[str, Any]] = [
            {"PK": "1", "a": "x"},
            {"PK": "2", "b": "y"},
        ]
        result = format_items_as_markdown(items)
        assert "a" in result
        assert "b" in result

    def test_long_values_truncated(self) -> None:
        items: list[dict[str, Any]] = [{"PK": "1", "data": "z" * 200}]
        result = format_items_as_markdown(items)
        assert "..." in result

    def test_pipe_escaped(self) -> None:
        items: list[dict[str, Any]] = [{"PK": "1", "val": "a|b"}]
        result = format_items_as_markdown(items)
        assert "\\|" in result


class TestBuildQueryResponse:
    def test_json_format(self) -> None:
        items: list[dict[str, Any]] = [{"PK": "1", "name": "test"}]
        result = build_query_response(items, 1, 1, None, ResponseFormat.JSON)
        data = json.loads(result)
        assert data["count"] == 1
        assert data["has_more"] is False
        assert len(data["items"]) == 1

    def test_json_with_pagination(self) -> None:
        last_key: dict[str, Any] = {"PK": "last"}
        result = build_query_response([], 0, 5, last_key, ResponseFormat.JSON)
        data = json.loads(result)
        assert data["has_more"] is True
        assert data["last_evaluated_key"] == {"PK": "last"}

    def test_markdown_format(self) -> None:
        items: list[dict[str, Any]] = [{"PK": "1", "val": "a"}]
        result = build_query_response(items, 1, 1, None, ResponseFormat.MARKDOWN)
        assert "**Results:**" in result
        assert "|" in result
        assert "1 items returned" in result
