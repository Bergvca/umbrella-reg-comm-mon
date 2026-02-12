"""Tests for umbrella_ingestion.s3 (NormalizedS3Store)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from umbrella_schema import Attachment, Channel, Direction, NormalizedMessage, Participant

from umbrella_ingestion.config import S3Config
from umbrella_ingestion.s3 import NormalizedS3Store


def _make_normalized_message(
    *,
    message_id: str = "<test@example.com>",
    channel: Channel = Channel.EMAIL,
    timestamp: datetime | None = None,
) -> NormalizedMessage:
    return NormalizedMessage(
        message_id=message_id,
        channel=channel,
        direction=Direction.INBOUND,
        timestamp=timestamp or datetime(2025, 6, 1, 12, 0, tzinfo=timezone.utc),
        participants=[Participant(id="a@b.com", name="Alice", role="sender")],
        body_text="Hello",
        metadata={"subject": "Test"},
    )


class TestNormalizedS3Store:
    @pytest.mark.asyncio
    async def test_start_creates_client(self, s3_config: S3Config):
        store = NormalizedS3Store(s3_config)
        with patch("umbrella_ingestion.s3.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = MagicMock()
            await store.start()
            assert store._client is not None

    @pytest.mark.asyncio
    async def test_stop_clears_client(self, s3_config: S3Config):
        store = NormalizedS3Store(s3_config)
        store._client = MagicMock()
        await store.stop()
        assert store._client is None

    @pytest.mark.asyncio
    async def test_store_puts_json_to_s3(self, s3_config: S3Config):
        store = NormalizedS3Store(s3_config)
        store._client = MagicMock()

        msg = _make_normalized_message()

        with patch("umbrella_ingestion.s3.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            uri = await store.store(msg)

        # Verify S3 key format
        assert uri.startswith("s3://test-bucket/normalized/email/2025/06/01/")
        assert uri.endswith(".json")

        # Verify put_object was called
        mock_thread.assert_awaited_once()
        call_args = mock_thread.call_args
        assert call_args[1]["Bucket"] == "test-bucket"
        assert call_args[1]["ContentType"] == "application/json"

    @pytest.mark.asyncio
    async def test_store_sanitizes_message_id(self, s3_config: S3Config):
        store = NormalizedS3Store(s3_config)
        store._client = MagicMock()

        msg = _make_normalized_message(message_id="<test/foo@example.com>")

        with patch("umbrella_ingestion.s3.asyncio.to_thread", new_callable=AsyncMock):
            uri = await store.store(msg)

        # Angle brackets and slashes should be sanitized
        assert "<" not in uri
        assert ">" not in uri

    @pytest.mark.asyncio
    async def test_store_with_custom_endpoint(self):
        config = S3Config(bucket="b", endpoint_url="http://minio:9000")
        store = NormalizedS3Store(config)
        store._client = MagicMock()

        msg = _make_normalized_message()
        with patch("umbrella_ingestion.s3.asyncio.to_thread", new_callable=AsyncMock):
            uri = await store.store(msg)

        assert uri.startswith("s3://b/")
