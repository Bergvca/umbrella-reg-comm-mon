"""Tests for umbrella_connector.dead_letter."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from umbrella_connector.dead_letter import DeadLetterHandler
from umbrella_connector.models import DeadLetterEnvelope, RawMessage


class TestDeadLetterHandler:
    @pytest.fixture
    def mock_producer(self) -> AsyncMock:
        producer = AsyncMock()
        producer.send_dead_letter = AsyncMock()
        return producer

    @pytest.fixture
    def handler(self, mock_producer: AsyncMock) -> DeadLetterHandler:
        return DeadLetterHandler(mock_producer, connector_name="test-connector")

    @pytest.mark.asyncio
    async def test_send_builds_envelope_and_publishes(
        self,
        handler: DeadLetterHandler,
        mock_producer: AsyncMock,
        raw_message: RawMessage,
    ):
        await handler.send(raw_message, error="Connection refused", attempts=5)

        mock_producer.send_dead_letter.assert_awaited_once()
        envelope: DeadLetterEnvelope = mock_producer.send_dead_letter.call_args[0][0]
        assert envelope.original_message.raw_message_id == "msg-001"
        assert envelope.connector_name == "test-connector"
        assert envelope.error == "Connection refused"
        assert envelope.attempts == 5

    @pytest.mark.asyncio
    async def test_send_preserves_original_message(
        self,
        handler: DeadLetterHandler,
        mock_producer: AsyncMock,
        raw_message: RawMessage,
    ):
        await handler.send(raw_message, error="timeout", attempts=3)

        envelope: DeadLetterEnvelope = mock_producer.send_dead_letter.call_args[0][0]
        assert envelope.original_message.channel == raw_message.channel
        assert envelope.original_message.raw_payload == raw_message.raw_payload
        assert envelope.original_message.attachment_refs == raw_message.attachment_refs

    @pytest.mark.asyncio
    async def test_send_with_different_connector_names(self, mock_producer: AsyncMock, raw_message: RawMessage):
        for name in ["teams-chat", "bloomberg-email", "unigy-turret"]:
            handler = DeadLetterHandler(mock_producer, connector_name=name)
            await handler.send(raw_message, error="err", attempts=1)
            envelope: DeadLetterEnvelope = mock_producer.send_dead_letter.call_args[0][0]
            assert envelope.connector_name == name
