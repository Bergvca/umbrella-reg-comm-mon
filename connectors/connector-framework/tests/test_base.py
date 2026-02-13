"""Tests for umbrella_connector.base (BaseConnector)."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest

from umbrella_connector.base import BaseConnector
from umbrella_connector.config import ConnectorConfig
from umbrella_connector.models import ConnectorStatus, RawMessage
from umbrella_schema import Channel


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_message(msg_id: str = "msg-1") -> RawMessage:
    return RawMessage(
        raw_message_id=msg_id,
        channel=Channel.TEAMS_CHAT,
        raw_payload={"text": "hello"},
    )


class FiniteConnector(BaseConnector):
    """Connector that yields a fixed list of messages then stops."""

    def __init__(self, config: ConnectorConfig, messages: list[RawMessage]) -> None:
        super().__init__(config)
        self._messages = messages

    async def ingest(self) -> AsyncIterator[RawMessage]:
        for msg in self._messages:
            yield msg


class ErrorConnector(BaseConnector):
    """Connector whose ingest raises after yielding some messages."""

    def __init__(self, config: ConnectorConfig, fail_after: int = 0) -> None:
        super().__init__(config)
        self._fail_after = fail_after

    async def ingest(self) -> AsyncIterator[RawMessage]:
        for i in range(self._fail_after):
            yield _make_message(f"msg-{i}")
        raise RuntimeError("source disconnected")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBaseConnectorInit:
    def test_initial_status(self, connector_config: ConnectorConfig):
        c = FiniteConnector(connector_config, [])
        assert c.status == ConnectorStatus.STARTING
        assert c.config.name == "test-connector"

    def test_subsystems_created(self, connector_config: ConnectorConfig):
        c = FiniteConnector(connector_config, [])
        assert c._producer is not None
        assert c._ingestion_client is not None
        assert c._dead_letter is not None
        assert isinstance(c._shutdown_event, asyncio.Event)


class TestDeliver:
    @pytest.mark.asyncio
    async def test_deliver_success(self, connector_config: ConnectorConfig):
        c = FiniteConnector(connector_config, [])
        c._producer.send_raw = AsyncMock()
        c._ingestion_client.submit = AsyncMock()
        c._dead_letter.send = AsyncMock()

        msg = _make_message()
        await c._deliver(msg)

        c._producer.send_raw.assert_awaited_once_with(msg)
        c._ingestion_client.submit.assert_awaited_once_with(msg)
        c._dead_letter.send.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_deliver_retries_then_succeeds(self, connector_config: ConnectorConfig):
        c = FiniteConnector(connector_config, [])
        call_count = 0

        async def flaky_send(message):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("transient")

        c._producer.send_raw = AsyncMock(side_effect=flaky_send)
        c._ingestion_client.submit = AsyncMock()
        c._dead_letter.send = AsyncMock()

        msg = _make_message()
        await c._deliver(msg)

        assert call_count == 2
        c._dead_letter.send.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_deliver_exhausts_retries_sends_dead_letter(self, connector_config: ConnectorConfig):
        c = FiniteConnector(connector_config, [])
        c._producer.send_raw = AsyncMock(side_effect=ConnectionError("down"))
        c._ingestion_client.submit = AsyncMock()
        c._dead_letter.send = AsyncMock()

        msg = _make_message()
        await c._deliver(msg)

        c._dead_letter.send.assert_awaited_once()
        call_kwargs = c._dead_letter.send.call_args
        assert call_kwargs[0][0] is msg
        assert "down" in call_kwargs[1]["error"]
        assert call_kwargs[1]["attempts"] == connector_config.retry.max_attempts
        # HTTP client should not be called if Kafka fails
        c._ingestion_client.submit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_deliver_kafka_succeeds_http_fails(self, connector_config: ConnectorConfig):
        """When Kafka succeeds but HTTP fails, message is NOT sent to DLQ."""
        c = FiniteConnector(connector_config, [])
        c._producer.send_raw = AsyncMock()
        c._ingestion_client.submit = AsyncMock(side_effect=ConnectionError("api unreachable"))
        c._dead_letter.send = AsyncMock()

        msg = _make_message()
        await c._deliver(msg)

        c._producer.send_raw.assert_awaited_once_with(msg)
        c._ingestion_client.submit.assert_awaited_once_with(msg)
        # HTTP failure does NOT trigger dead-letter
        c._dead_letter.send.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_deliver_with_disabled_http_client(self, connector_config: ConnectorConfig):
        """When HTTP client is disabled, only Kafka delivery happens."""
        c = FiniteConnector(connector_config, [])
        c._producer.send_raw = AsyncMock()
        # Simulate disabled client (submit is no-op)
        c._ingestion_client.submit = AsyncMock()
        c._dead_letter.send = AsyncMock()

        msg = _make_message()
        await c._deliver(msg)

        c._producer.send_raw.assert_awaited_once_with(msg)
        c._ingestion_client.submit.assert_awaited_once()
        c._dead_letter.send.assert_not_awaited()


class TestIngestLoop:
    @pytest.mark.asyncio
    async def test_processes_all_messages(self, connector_config: ConnectorConfig):
        messages = [_make_message(f"msg-{i}") for i in range(3)]
        c = FiniteConnector(connector_config, messages)
        c._producer.send_raw = AsyncMock()
        c._ingestion_client.submit = AsyncMock()

        await c._run_ingest_loop()

        assert c._producer.send_raw.await_count == 3
        assert c._ingestion_client.submit.await_count == 3
        assert c.status == ConnectorStatus.RUNNING

    @pytest.mark.asyncio
    async def test_stops_on_shutdown_event(self, connector_config: ConnectorConfig):
        delivered = []

        class SlowConnector(BaseConnector):
            async def ingest(self) -> AsyncIterator[RawMessage]:
                for i in range(100):
                    yield _make_message(f"msg-{i}")

        c = SlowConnector(connector_config)

        async def track_send(msg):
            delivered.append(msg)
            if len(delivered) >= 2:
                c._shutdown_event.set()

        c._producer.send_raw = AsyncMock(side_effect=track_send)
        c._ingestion_client.submit = AsyncMock()

        await c._run_ingest_loop()

        # Should have stopped after ~2-3 messages (shutdown set after 2nd send_raw)
        assert len(delivered) <= 4

    @pytest.mark.asyncio
    async def test_error_sets_degraded(self, connector_config: ConnectorConfig):
        c = ErrorConnector(connector_config, fail_after=0)
        c._producer.send_raw = AsyncMock()
        c._ingestion_client.submit = AsyncMock()

        with pytest.raises(RuntimeError, match="source disconnected"):
            await c._run_ingest_loop()

        assert c.status == ConnectorStatus.DEGRADED

    @pytest.mark.asyncio
    async def test_empty_ingest(self, connector_config: ConnectorConfig):
        c = FiniteConnector(connector_config, [])
        c._producer.send_raw = AsyncMock()
        c._ingestion_client.submit = AsyncMock()

        await c._run_ingest_loop()

        c._producer.send_raw.assert_not_awaited()
        assert c.status == ConnectorStatus.RUNNING


class TestRun:
    @pytest.mark.asyncio
    async def test_run_lifecycle(self, connector_config: ConnectorConfig):
        """Test that run() starts subsystems, runs ingest, and shuts down."""
        messages = [_make_message("lifecycle-1")]
        c = FiniteConnector(connector_config, messages)

        # Mock all infrastructure
        c._producer.start = AsyncMock()
        c._producer.stop = AsyncMock()
        c._producer.send_raw = AsyncMock()
        c._ingestion_client.start = AsyncMock()
        c._ingestion_client.stop = AsyncMock()
        c._ingestion_client.submit = AsyncMock()

        # Patch the health server to just wait for shutdown (avoid port binding)
        async def fake_health_server():
            await c._shutdown_event.wait()

        with patch.object(c, "_run_health_server", side_effect=fake_health_server):
            # The ingest loop will finish (finite messages), but the health
            # server blocks. We need to set shutdown after ingest completes.
            original_ingest_loop = c._run_ingest_loop

            async def ingest_then_shutdown():
                await original_ingest_loop()
                c._shutdown_event.set()

            with patch.object(c, "_run_ingest_loop", side_effect=ingest_then_shutdown):
                await c.run()

        c._producer.start.assert_awaited_once()
        c._ingestion_client.start.assert_awaited_once()
        c._producer.stop.assert_awaited_once()
        c._ingestion_client.stop.assert_awaited_once()
        assert c.status == ConnectorStatus.STOPPED
