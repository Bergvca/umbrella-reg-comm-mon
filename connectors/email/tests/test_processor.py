"""Tests for umbrella_email.processor (Stage 2 — EmailProcessor)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from umbrella_email.config import EmailProcessorConfig, S3Config
from umbrella_email.parser import ParsedAttachment, ParsedEmail
from umbrella_email.processor import EmailProcessor

from tests.conftest import _build_multipart_email


@pytest.fixture
def processor(processor_config: EmailProcessorConfig) -> EmailProcessor:
    return EmailProcessor(processor_config)


def _make_kafka_message(
    *,
    raw_message_id: str = "msg-001",
    channel: str = "email",
    raw_format: str = "eml_ref",
    s3_uri: str = "s3://bucket/raw/email/100.eml",
) -> MagicMock:
    """Create a mock Kafka consumer message."""
    msg = MagicMock()
    msg.value = {
        "raw_message_id": raw_message_id,
        "channel": channel,
        "raw_format": raw_format,
        "raw_payload": {
            "s3_uri": s3_uri,
            "size_bytes": 1024,
            "envelope": {"subject": "Test"},
        },
        "metadata": {"imap_uid": "100"},
    }
    return msg


class TestEmailProcessorInit:
    def test_initial_state(self, processor: EmailProcessor):
        assert processor._messages_processed == 0
        assert processor._consumer is None
        assert processor._producer is None


class TestEmailProcessorProcessMessage:
    @pytest.mark.asyncio
    async def test_process_message_downloads_parses_uploads(
        self, processor: EmailProcessor
    ):
        raw_eml = _build_multipart_email(
            body_text="Hello",
            body_html="<p>Hello</p>",
            attachments=[("file.txt", "text/plain", b"content")],
        )

        # Mock S3
        processor._s3 = AsyncMock()
        processor._s3.download_raw_eml = AsyncMock(return_value=raw_eml)
        processor._s3.upload_attachments = AsyncMock(
            return_value=["s3://bucket/attachments/100/abc_file.txt"]
        )

        # Mock Kafka producer
        processor._producer = AsyncMock()
        processor._producer.send_and_wait = AsyncMock()

        raw_message = _make_kafka_message().value
        await processor._process_message(raw_message)

        # S3 download called
        processor._s3.download_raw_eml.assert_awaited_once_with(
            "s3://bucket/raw/email/100.eml"
        )

        # Attachments uploaded
        processor._s3.upload_attachments.assert_awaited_once()

        # Published to output topic
        processor._producer.send_and_wait.assert_awaited_once()
        call_args = processor._producer.send_and_wait.call_args
        assert call_args[0][0] == "parsed-messages"  # topic

        # Verify output shape
        output = json.loads(call_args[1]["value"])
        assert output["raw_message_id"] == "msg-001"
        assert output["channel"] == "email"
        assert output["subject"] == "Multipart Email"
        assert output["body_text"] is not None
        assert output["body_html"] is not None
        assert len(output["attachment_refs"]) == 1
        assert output["raw_eml_s3_uri"] == "s3://bucket/raw/email/100.eml"

    @pytest.mark.asyncio
    async def test_process_message_no_attachments(self, processor: EmailProcessor):
        from tests.conftest import _build_plain_email

        raw_eml = _build_plain_email()

        processor._s3 = AsyncMock()
        processor._s3.download_raw_eml = AsyncMock(return_value=raw_eml)
        processor._s3.upload_attachments = AsyncMock(return_value=[])
        processor._producer = AsyncMock()
        processor._producer.send_and_wait = AsyncMock()

        await processor._process_message(_make_kafka_message().value)

        output = json.loads(
            processor._producer.send_and_wait.call_args[1]["value"]
        )
        assert output["attachment_refs"] == []


class TestEmailProcessorConsumeLoop:
    @pytest.mark.asyncio
    async def test_skips_non_email_messages(self, processor: EmailProcessor):
        non_email = _make_kafka_message(channel="teams_chat")

        processor._consumer = AsyncMock()
        processor._consumer.commit = AsyncMock()
        processor._producer = AsyncMock()

        # Make the consumer yield one non-email message then stop
        async def fake_consumer():
            yield non_email
            processor._shutdown_event.set()

        processor._consumer.__aiter__ = lambda self: fake_consumer()

        await processor._consume_loop()

        # Producer should not have been called (no message processed)
        processor._producer.send_and_wait = AsyncMock()
        assert processor._messages_processed == 0

    @pytest.mark.asyncio
    async def test_skips_non_eml_ref_format(self, processor: EmailProcessor):
        wrong_format = _make_kafka_message(raw_format="json")

        processor._consumer = AsyncMock()
        processor._consumer.commit = AsyncMock()
        processor._producer = AsyncMock()

        async def fake_consumer():
            yield wrong_format
            processor._shutdown_event.set()

        processor._consumer.__aiter__ = lambda self: fake_consumer()

        await processor._consume_loop()
        assert processor._messages_processed == 0

    @pytest.mark.asyncio
    async def test_commits_on_processing_error(self, processor: EmailProcessor):
        msg = _make_kafka_message()

        processor._consumer = AsyncMock()
        processor._consumer.commit = AsyncMock()
        processor._producer = AsyncMock()
        processor._s3 = AsyncMock()
        processor._s3.download_raw_eml = AsyncMock(side_effect=Exception("S3 down"))

        async def fake_consumer():
            yield msg
            processor._shutdown_event.set()

        processor._consumer.__aiter__ = lambda self: fake_consumer()

        await processor._consume_loop()

        # Should still commit (poison pill avoidance — raw is safe in S3)
        assert processor._consumer.commit.await_count >= 1
        assert processor._messages_processed == 0
