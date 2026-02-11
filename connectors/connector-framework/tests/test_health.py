"""Tests for umbrella_connector.health."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock

import httpx
import pytest

from umbrella_connector.base import BaseConnector
from umbrella_connector.config import ConnectorConfig
from umbrella_connector.health import create_health_app
from umbrella_connector.models import ConnectorStatus, RawMessage
from umbrella_schema import Channel


class StubConnector(BaseConnector):
    """Minimal concrete connector for health endpoint testing."""

    async def ingest(self) -> AsyncIterator[RawMessage]:
        yield RawMessage(
            raw_message_id="stub",
            channel=Channel.EMAIL,
            raw_payload={},
        )


@pytest.fixture
def connector(connector_config: ConnectorConfig) -> StubConnector:
    c = StubConnector(connector_config)
    c.start_time = time.monotonic()
    return c


@pytest.fixture
def health_app(connector: StubConnector):
    return create_health_app(connector)


class TestHealthEndpoints:
    @pytest.mark.asyncio
    async def test_health_starting(self, health_app, connector: StubConnector):
        connector.status = ConnectorStatus.STARTING
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=health_app),
            base_url="http://test",
        ) as client:
            resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["connector_name"] == "test-connector"
        assert data["status"] == "starting"
        assert "uptime_seconds" in data

    @pytest.mark.asyncio
    async def test_health_running(self, health_app, connector: StubConnector):
        connector.status = ConnectorStatus.RUNNING
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=health_app),
            base_url="http://test",
        ) as client:
            resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "running"

    @pytest.mark.asyncio
    async def test_health_degraded_returns_503(self, health_app, connector: StubConnector):
        connector.status = ConnectorStatus.DEGRADED
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=health_app),
            base_url="http://test",
        ) as client:
            resp = await client.get("/health")
        assert resp.status_code == 503
        assert resp.json()["status"] == "degraded"

    @pytest.mark.asyncio
    async def test_health_stopped_returns_503(self, health_app, connector: StubConnector):
        connector.status = ConnectorStatus.STOPPED
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=health_app),
            base_url="http://test",
        ) as client:
            resp = await client.get("/health")
        assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_ready_when_running(self, health_app, connector: StubConnector):
        connector.status = ConnectorStatus.RUNNING
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=health_app),
            base_url="http://test",
        ) as client:
            resp = await client.get("/ready")
        assert resp.status_code == 200
        assert resp.json()["ready"] is True

    @pytest.mark.asyncio
    async def test_ready_when_not_running(self, health_app, connector: StubConnector):
        for status in [ConnectorStatus.STARTING, ConnectorStatus.DEGRADED, ConnectorStatus.STOPPED]:
            connector.status = status
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=health_app),
                base_url="http://test",
            ) as client:
                resp = await client.get("/ready")
            assert resp.status_code == 503
            assert resp.json()["ready"] is False

    @pytest.mark.asyncio
    async def test_health_includes_custom_details(self, connector_config: ConnectorConfig):
        class DetailConnector(BaseConnector):
            async def ingest(self) -> AsyncIterator[RawMessage]:
                yield RawMessage(
                    raw_message_id="x",
                    channel=Channel.EMAIL,
                    raw_payload={},
                )

            async def health_check(self) -> dict[str, object]:
                return {"last_poll": "2025-06-01T00:00:00Z", "messages_processed": 42}

        c = DetailConnector(connector_config)
        c.start_time = time.monotonic()
        c.status = ConnectorStatus.RUNNING
        app = create_health_app(c)

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get("/health")
        data = resp.json()
        assert data["details"]["messages_processed"] == 42
        assert data["details"]["last_poll"] == "2025-06-01T00:00:00Z"
