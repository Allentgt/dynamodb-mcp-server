"""Shared test fixtures for DynamoDB MCP server tests.

Provides mock DynamoDB tables and a fake MCP context that tools can use
without requiring a real MCP server or AWS credentials.

Works around the moto + aiobotocore incompatibility (aiobotocore >=2.11.0 expects
async aiohttp responses but moto returns sync botocore responses) by wrapping
synchronous boto3 objects in async-compatible shims that match the interface
our tool handlers use.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

import boto3
import pytest
from moto import mock_aws

from dynamodb_mcp_server.server import AppContext


@dataclass
class FakeLifespanContext:
    """Mimics the lifespan context structure tools access via ctx."""

    lifespan_context: AppContext


@dataclass
class FakeContext:
    """Minimal fake for mcp.server.fastmcp.Context used by tool handlers.

    Provides the request_context.lifespan_context.session path that
    all tools use to obtain the aioboto3 session.
    """

    request_context: FakeLifespanContext

    @staticmethod
    def info(msg: str) -> None:
        """No-op logger matching Context.info signature."""

    @staticmethod
    def debug(msg: str) -> None:
        """No-op logger matching Context.debug signature."""


TEST_REGION = "us-east-1"


class AsyncBatchWriter:
    """Wraps a synchronous boto3 batch_writer to present an async interface."""

    def __init__(self, sync_batch_writer: Any) -> None:
        self._writer = sync_batch_writer

    async def put_item(self, **kwargs: Any) -> None:
        self._writer.put_item(**kwargs)

    async def delete_item(self, **kwargs: Any) -> None:
        self._writer.delete_item(**kwargs)

    async def __aenter__(self) -> AsyncBatchWriter:
        self._writer.__enter__()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self._writer.__exit__(exc_type, exc_val, exc_tb)


class AsyncTable:
    """Wraps a synchronous boto3 Table to present an async interface."""

    def __init__(self, sync_table: Any) -> None:
        self._table = sync_table

    async def query(self, **kwargs: Any) -> dict[str, Any]:
        return self._table.query(**kwargs)

    async def scan(self, **kwargs: Any) -> dict[str, Any]:
        return self._table.scan(**kwargs)

    async def put_item(self, **kwargs: Any) -> dict[str, Any]:
        return self._table.put_item(**kwargs)

    async def delete_item(self, **kwargs: Any) -> dict[str, Any]:
        return self._table.delete_item(**kwargs)

    async def update_item(self, **kwargs: Any) -> dict[str, Any]:
        return self._table.update_item(**kwargs)

    def batch_writer(self) -> AsyncBatchWriter:
        return AsyncBatchWriter(self._table.batch_writer())


class AsyncResource:
    """Wraps a synchronous boto3 DynamoDB resource to present an async interface."""

    def __init__(self, sync_resource: Any) -> None:
        self._resource = sync_resource

    async def Table(self, name: str) -> AsyncTable:  # noqa: N802
        return AsyncTable(self._resource.Table(name))


class AsyncClient:
    """Wraps a synchronous boto3 DynamoDB client to present an async interface."""

    def __init__(self, sync_client: Any) -> None:
        self._client = sync_client

    async def list_tables(self, **kwargs: Any) -> dict[str, Any]:
        return self._client.list_tables(**kwargs)

    async def describe_table(self, **kwargs: Any) -> dict[str, Any]:
        return self._client.describe_table(**kwargs)

    async def update_table(self, **kwargs: Any) -> dict[str, Any]:
        return self._client.update_table(**kwargs)


class MockSession:
    """Drop-in replacement for aioboto3.Session that uses sync boto3 under moto.

    Provides .client() and .resource() as async context managers that return
    the async wrapper objects above.
    """

    def __init__(self, region_name: str = TEST_REGION) -> None:
        self._region = region_name

    @asynccontextmanager
    async def client(self, service_name: str, **kwargs: Any):
        sync_client = boto3.client(service_name, region_name=self._region, **kwargs)
        try:
            yield AsyncClient(sync_client)
        finally:
            pass

    @asynccontextmanager
    async def resource(self, service_name: str, **kwargs: Any):
        sync_resource = boto3.resource(service_name, region_name=self._region, **kwargs)
        try:
            yield AsyncResource(sync_resource)
        finally:
            pass


def make_ctx(session: MockSession) -> FakeContext:
    """Build a fake MCP context wrapping the given mock session."""
    app = AppContext(session=session, region=TEST_REGION)  # type: ignore[arg-type]
    return FakeContext(request_context=FakeLifespanContext(lifespan_context=app))


@pytest.fixture()
def aws_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set AWS environment variables for moto."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", TEST_REGION)
    monkeypatch.setenv("AWS_REGION", TEST_REGION)


@pytest.fixture()
def mock_dynamodb(aws_env: None):
    """Start moto mock for all AWS services and yield."""
    with mock_aws():
        yield


@pytest.fixture()
def dynamodb_resource(mock_dynamodb: None):
    """Synchronous boto3 DynamoDB resource for creating test tables."""
    return boto3.resource("dynamodb", region_name=TEST_REGION)


@pytest.fixture()
def ctx(mock_dynamodb: None) -> FakeContext:
    """Fake MCP context with a MockSession pointing at moto."""
    session = MockSession(region_name=TEST_REGION)
    return make_ctx(session)


@pytest.fixture()
def simple_table(dynamodb_resource: Any) -> str:
    """Create a simple hash-key-only test table. Returns the table name."""
    table_name = "test-simple"
    dynamodb_resource.create_table(
        TableName=table_name,
        KeySchema=[{"AttributeName": "PK", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "PK", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    return table_name


@pytest.fixture()
def composite_table(dynamodb_resource: Any) -> str:
    """Create a table with hash + range key. Returns the table name."""
    table_name = "test-composite"
    dynamodb_resource.create_table(
        TableName=table_name,
        KeySchema=[
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    return table_name


@pytest.fixture()
def populated_table(dynamodb_resource: Any, composite_table: str) -> str:
    """Composite table pre-loaded with sample items. Returns the table name."""
    table = dynamodb_resource.Table(composite_table)
    items = [
        {"PK": "USER#1", "SK": "PROFILE", "name": "Alice", "age": 30, "active": True},
        {"PK": "USER#1", "SK": "ORDER#001", "total": 99, "status": "shipped"},
        {"PK": "USER#1", "SK": "ORDER#002", "total": 150, "status": "pending"},
        {"PK": "USER#2", "SK": "PROFILE", "name": "Bob", "age": 25, "active": False},
        {"PK": "USER#2", "SK": "ORDER#003", "total": 200, "status": "shipped"},
    ]
    with table.batch_writer() as batch:
        for item in items:
            batch.put_item(Item=item)
    return composite_table
