"""Tests for umbrella_connector.interface."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime, timezone

import pytest

from umbrella_connector.interface import ConnectorInterface
from umbrella_connector.models import BackfillRequest, RawMessage
from umbrella_schema import Channel


class TestConnectorInterface:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError, match="abstract method"):
            ConnectorInterface()  # type: ignore[abstract]

    def test_concrete_subclass_with_ingest(self):
        class MinimalConnector(ConnectorInterface):
            async def ingest(self) -> AsyncIterator[RawMessage]:
                yield RawMessage(
                    raw_message_id="test",
                    channel=Channel.EMAIL,
                    raw_payload={},
                )

        connector = MinimalConnector()
        assert isinstance(connector, ConnectorInterface)

    @pytest.mark.asyncio
    async def test_default_health_check(self):
        class Conn(ConnectorInterface):
            async def ingest(self) -> AsyncIterator[RawMessage]:
                yield RawMessage(
                    raw_message_id="x",
                    channel=Channel.EMAIL,
                    raw_payload={},
                )

        result = await Conn().health_check()
        assert result == {}

    def test_default_backfill_raises(self):
        class Conn(ConnectorInterface):
            async def ingest(self) -> AsyncIterator[RawMessage]:
                yield RawMessage(
                    raw_message_id="x",
                    channel=Channel.EMAIL,
                    raw_payload={},
                )

        req = BackfillRequest(
            start=datetime(2025, 1, 1, tzinfo=timezone.utc),
            end=datetime(2025, 1, 2, tzinfo=timezone.utc),
            channel=Channel.EMAIL,
        )
        with pytest.raises(NotImplementedError, match="Conn does not support backfill"):
            Conn().backfill(req)

    @pytest.mark.asyncio
    async def test_custom_health_check(self):
        class Conn(ConnectorInterface):
            async def ingest(self) -> AsyncIterator[RawMessage]:
                yield RawMessage(
                    raw_message_id="x",
                    channel=Channel.EMAIL,
                    raw_payload={},
                )

            async def health_check(self) -> dict[str, object]:
                return {"connected": True, "queue_depth": 42}

        result = await Conn().health_check()
        assert result["connected"] is True
        assert result["queue_depth"] == 42

    @pytest.mark.asyncio
    async def test_custom_backfill(self):
        class Conn(ConnectorInterface):
            async def ingest(self) -> AsyncIterator[RawMessage]:
                yield RawMessage(
                    raw_message_id="x",
                    channel=Channel.EMAIL,
                    raw_payload={},
                )

            async def backfill(self, request: BackfillRequest) -> AsyncIterator[RawMessage]:
                yield RawMessage(
                    raw_message_id="backfill-1",
                    channel=request.channel,
                    raw_payload={"backfilled": True},
                )

        req = BackfillRequest(
            start=datetime(2025, 1, 1, tzinfo=timezone.utc),
            end=datetime(2025, 1, 2, tzinfo=timezone.utc),
            channel=Channel.TEAMS_CHAT,
        )
        messages = [m async for m in Conn().backfill(req)]
        assert len(messages) == 1
        assert messages[0].raw_message_id == "backfill-1"
        assert messages[0].channel == Channel.TEAMS_CHAT

    @pytest.mark.asyncio
    async def test_ingest_yields_messages(self):
        class Conn(ConnectorInterface):
            async def ingest(self) -> AsyncIterator[RawMessage]:
                for i in range(3):
                    yield RawMessage(
                        raw_message_id=f"msg-{i}",
                        channel=Channel.BLOOMBERG_EMAIL,
                        raw_payload={"index": i},
                    )

        messages = [m async for m in Conn().ingest()]
        assert len(messages) == 3
        assert [m.raw_message_id for m in messages] == ["msg-0", "msg-1", "msg-2"]
