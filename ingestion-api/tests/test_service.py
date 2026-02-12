"""Tests for umbrella_ingestion.service (IngestionService)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from umbrella_ingestion.config import IngestionConfig, KafkaConsumerConfig, S3Config
from umbrella_ingestion.service import IngestionService

from tests.conftest import make_parsed_email


def _make_kafka_message(parsed: dict) -> MagicMock:
    """Wrap a parsed dict as a mock Kafka consumer record."""
    msg = MagicMock()
    msg.value = parsed
    return msg


@pytest.fixture
def service(ingestion_config: IngestionConfig) -> IngestionService:
    return IngestionService(ingestion_config)


class TestIngestionServiceInit:
    def test_initial_state(self, service: IngestionService):
        assert service.messages_processed == 0
        assert service.messages_skipped == 0
        assert service.messages_failed == 0
        assert service.is_ready is False
        assert "email" in service.supported_channels


class TestConsumeLoop:
    @pytest.mark.asyncio
    async def test_normalizes_email_message(self, service: IngestionService):
        parsed = make_parsed_email(
            from_address="external@gmail.com",
            to=["user@acme.com"],
        )
        kafka_msg = _make_kafka_message(parsed)

        # Mock consumer, producer, S3
        service._consumer = AsyncMock()
        service._consumer.commit = AsyncMock()
        service._producer = AsyncMock()
        service._producer.send_and_wait = AsyncMock()
        service._s3 = AsyncMock()
        service._s3.store = AsyncMock(return_value="s3://bucket/normalized/email/2025/06/01/abc.json")

        async def fake_consumer():
            yield kafka_msg
            service._shutdown_event.set()

        service._consumer.__aiter__ = lambda self: fake_consumer()

        await service._consume_loop()

        assert service.messages_processed == 1
        assert service.messages_skipped == 0
        assert service.messages_failed == 0

        # Verify Kafka publish
        service._producer.send_and_wait.assert_awaited_once()
        call_args = service._producer.send_and_wait.call_args
        assert call_args[0][0] == "normalized-messages"
        output = json.loads(call_args[1]["value"])
        assert output["channel"] == "email"
        assert output["direction"] == "inbound"
        assert len(output["participants"]) >= 2

        # Verify S3 store
        service._s3.store.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_skips_unsupported_channel(self, service: IngestionService):
        parsed = {"channel": "teams_chat", "message_id": "x"}
        kafka_msg = _make_kafka_message(parsed)

        service._consumer = AsyncMock()
        service._consumer.commit = AsyncMock()
        service._producer = AsyncMock()

        async def fake_consumer():
            yield kafka_msg
            service._shutdown_event.set()

        service._consumer.__aiter__ = lambda self: fake_consumer()

        await service._consume_loop()

        assert service.messages_skipped == 1
        assert service.messages_processed == 0

    @pytest.mark.asyncio
    async def test_commits_on_normalization_error(self, service: IngestionService):
        # Invalid parsed message — missing required fields
        parsed = {"channel": "email", "message_id": "x"}
        kafka_msg = _make_kafka_message(parsed)

        service._consumer = AsyncMock()
        service._consumer.commit = AsyncMock()
        service._producer = AsyncMock()

        async def fake_consumer():
            yield kafka_msg
            service._shutdown_event.set()

        service._consumer.__aiter__ = lambda self: fake_consumer()

        await service._consume_loop()

        # Should commit to avoid poison pill
        assert service._consumer.commit.await_count >= 1
        assert service.messages_failed == 1
        assert service.messages_processed == 0

    @pytest.mark.asyncio
    async def test_commits_on_dual_write_error(self, service: IngestionService):
        parsed = make_parsed_email(
            from_address="external@gmail.com",
            to=["user@acme.com"],
        )
        kafka_msg = _make_kafka_message(parsed)

        service._consumer = AsyncMock()
        service._consumer.commit = AsyncMock()
        service._producer = AsyncMock()
        service._producer.send_and_wait = AsyncMock(side_effect=Exception("Kafka down"))
        service._s3 = AsyncMock()

        async def fake_consumer():
            yield kafka_msg
            service._shutdown_event.set()

        service._consumer.__aiter__ = lambda self: fake_consumer()

        await service._consume_loop()

        assert service.messages_failed == 1
        assert service._consumer.commit.await_count >= 1


class TestDualWrite:
    @pytest.mark.asyncio
    async def test_writes_to_kafka_and_s3(self, service: IngestionService):
        from umbrella_ingestion.normalizers.email import EmailNormalizer

        normalizer = EmailNormalizer(monitored_domains=["acme.com"])
        parsed = make_parsed_email(
            from_address="external@gmail.com",
            to=["user@acme.com"],
        )
        normalized = normalizer.normalize(parsed)

        service._producer = AsyncMock()
        service._producer.send_and_wait = AsyncMock()
        service._s3 = AsyncMock()
        service._s3.store = AsyncMock(return_value="s3://bucket/normalized/email/2025/06/01/abc.json")

        await service._dual_write(normalized)

        # Kafka
        service._producer.send_and_wait.assert_awaited_once()
        call_args = service._producer.send_and_wait.call_args
        assert call_args[0][0] == "normalized-messages"
        assert call_args[1]["key"] == normalized.message_id.encode("utf-8")

        # S3
        service._s3.store.assert_awaited_once_with(normalized)
