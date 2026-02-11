"""Tests for umbrella_connector.kafka_producer."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from umbrella_connector.config import KafkaConfig
from umbrella_connector.kafka_producer import KafkaProducerWrapper
from umbrella_connector.models import DeadLetterEnvelope, RawMessage
from umbrella_schema import Channel


@pytest.fixture
def wrapper(kafka_config: KafkaConfig) -> KafkaProducerWrapper:
    return KafkaProducerWrapper(kafka_config)


class TestKafkaProducerWrapper:
    @pytest.mark.asyncio
    async def test_start_creates_producer(self, wrapper: KafkaProducerWrapper):
        with patch("umbrella_connector.kafka_producer.AIOKafkaProducer") as MockProducer:
            mock_instance = AsyncMock()
            MockProducer.return_value = mock_instance
            await wrapper.start()
            MockProducer.assert_called_once()
            mock_instance.start.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_stop_when_not_started(self, wrapper: KafkaProducerWrapper):
        # Should not raise when producer is None
        await wrapper.stop()

    @pytest.mark.asyncio
    async def test_stop_calls_producer_stop(self, wrapper: KafkaProducerWrapper):
        with patch("umbrella_connector.kafka_producer.AIOKafkaProducer") as MockProducer:
            mock_instance = AsyncMock()
            MockProducer.return_value = mock_instance
            await wrapper.start()
            await wrapper.stop()
            mock_instance.stop.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_send_raw(self, wrapper: KafkaProducerWrapper, raw_message: RawMessage):
        with patch("umbrella_connector.kafka_producer.AIOKafkaProducer") as MockProducer:
            mock_instance = AsyncMock()
            MockProducer.return_value = mock_instance
            await wrapper.start()

            await wrapper.send_raw(raw_message)

            mock_instance.send_and_wait.assert_awaited_once()
            call_args = mock_instance.send_and_wait.call_args
            assert call_args[0][0] == "raw-messages"
            # Verify the value is valid JSON containing the message ID
            sent_value = call_args[1]["value"]
            parsed = json.loads(sent_value)
            assert parsed["raw_message_id"] == "msg-001"
            # Verify the key is the message ID
            assert call_args[1]["key"] == b"msg-001"

    @pytest.mark.asyncio
    async def test_send_dead_letter(self, wrapper: KafkaProducerWrapper, raw_message: RawMessage):
        envelope = DeadLetterEnvelope(
            original_message=raw_message,
            connector_name="test",
            error="boom",
            attempts=3,
        )

        with patch("umbrella_connector.kafka_producer.AIOKafkaProducer") as MockProducer:
            mock_instance = AsyncMock()
            MockProducer.return_value = mock_instance
            await wrapper.start()

            await wrapper.send_dead_letter(envelope)

            mock_instance.send_and_wait.assert_awaited_once()
            call_args = mock_instance.send_and_wait.call_args
            assert call_args[0][0] == "dead-letter"
            sent_value = call_args[1]["value"]
            parsed = json.loads(sent_value)
            assert parsed["connector_name"] == "test"
            assert parsed["error"] == "boom"
            assert parsed["original_message"]["raw_message_id"] == "msg-001"

    @pytest.mark.asyncio
    async def test_send_raw_not_started_raises(
        self, wrapper: KafkaProducerWrapper, raw_message: RawMessage
    ):
        with pytest.raises(AssertionError, match="Producer not started"):
            await wrapper.send_raw(raw_message)

    @pytest.mark.asyncio
    async def test_send_dead_letter_not_started_raises(
        self, wrapper: KafkaProducerWrapper, raw_message: RawMessage
    ):
        envelope = DeadLetterEnvelope(
            original_message=raw_message,
            connector_name="test",
            error="err",
            attempts=1,
        )
        with pytest.raises(AssertionError, match="Producer not started"):
            await wrapper.send_dead_letter(envelope)
