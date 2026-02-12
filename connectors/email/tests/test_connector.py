"""Tests for umbrella_email.connector (Stage 1 — EmailConnector)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from umbrella_connector import BackfillRequest, RawMessage
from umbrella_email.config import EmailConnectorConfig
from umbrella_email.connector import EmailConnector
from umbrella_email.imap_client import FetchedEmail
from umbrella_schema import Channel

from tests.conftest import _build_plain_email


def _make_fetched(uid: str = "100") -> FetchedEmail:
    raw = _build_plain_email(message_id=f"<msg-{uid}@example.com>")
    return FetchedEmail(uid=uid, raw_bytes=raw)


class TestEmailConnectorInit:
    def test_initial_state(self, connector_config: EmailConnectorConfig):
        c = EmailConnector(connector_config)
        assert c.config.name == "email-test"
        assert c._messages_ingested == 0
        assert c._last_poll_time is None


class TestEmailConnectorIngest:
    @pytest.mark.asyncio
    async def test_yields_raw_messages(self, connector_config: EmailConnectorConfig):
        c = EmailConnector(connector_config)
        c._imap = AsyncMock()
        c._imap.connect = AsyncMock()
        c._imap.disconnect = AsyncMock()
        c._imap.poll_new_messages = AsyncMock(
            side_effect=[
                [_make_fetched("1"), _make_fetched("2")],
                [],  # second poll returns empty → we'll stop
            ]
        )
        c._s3 = AsyncMock()
        c._s3.start = AsyncMock()
        c._s3.stop = AsyncMock()
        c._s3.upload_raw_eml = AsyncMock(return_value="s3://bucket/raw/email/1.eml")

        # Mock the framework's infrastructure
        c._producer.send_raw = AsyncMock()
        c._ingestion_client.submit = AsyncMock()

        messages: list[RawMessage] = []
        count = 0
        async for msg in c.ingest():
            messages.append(msg)
            count += 1
            if count >= 2:
                break

        assert len(messages) == 2
        assert all(m.channel == Channel.EMAIL for m in messages)
        assert all(m.raw_format == "eml_ref" for m in messages)

    @pytest.mark.asyncio
    async def test_raw_message_structure(self, connector_config: EmailConnectorConfig):
        c = EmailConnector(connector_config)
        c._imap = AsyncMock()
        c._imap.connect = AsyncMock()
        c._imap.disconnect = AsyncMock()
        c._imap.poll_new_messages = AsyncMock(return_value=[_make_fetched("42")])
        c._s3 = AsyncMock()
        c._s3.start = AsyncMock()
        c._s3.stop = AsyncMock()
        c._s3.upload_raw_eml = AsyncMock(return_value="s3://bucket/raw/email/42.eml")
        c._producer.send_raw = AsyncMock()
        c._ingestion_client.submit = AsyncMock()

        async for msg in c.ingest():
            assert msg.raw_payload["s3_uri"] == "s3://bucket/raw/email/42.eml"
            assert "envelope" in msg.raw_payload
            assert msg.raw_payload["envelope"]["subject"] == "Test Subject"
            assert msg.raw_payload["size_bytes"] > 0
            assert msg.metadata["imap_uid"] == "42"
            assert msg.metadata["mailbox"] == "INBOX"
            break

    @pytest.mark.asyncio
    async def test_s3_upload_called_before_yield(self, connector_config: EmailConnectorConfig):
        c = EmailConnector(connector_config)
        c._imap = AsyncMock()
        c._imap.connect = AsyncMock()
        c._imap.disconnect = AsyncMock()
        c._imap.poll_new_messages = AsyncMock(return_value=[_make_fetched("1")])
        c._s3 = AsyncMock()
        c._s3.start = AsyncMock()
        c._s3.stop = AsyncMock()
        c._s3.upload_raw_eml = AsyncMock(return_value="s3://b/1.eml")
        c._producer.send_raw = AsyncMock()
        c._ingestion_client.submit = AsyncMock()

        async for _ in c.ingest():
            # By the time we get the message, S3 upload must have happened
            c._s3.upload_raw_eml.assert_awaited_once()
            break

    @pytest.mark.asyncio
    async def test_messages_ingested_counter(self, connector_config: EmailConnectorConfig):
        c = EmailConnector(connector_config)
        c._imap = AsyncMock()
        c._imap.connect = AsyncMock()
        c._imap.disconnect = AsyncMock()
        c._imap.poll_new_messages = AsyncMock(
            return_value=[_make_fetched("1"), _make_fetched("2"), _make_fetched("3")]
        )
        c._s3 = AsyncMock()
        c._s3.start = AsyncMock()
        c._s3.stop = AsyncMock()
        c._s3.upload_raw_eml = AsyncMock(return_value="s3://b/x.eml")
        c._producer.send_raw = AsyncMock()
        c._ingestion_client.submit = AsyncMock()

        count = 0
        async for _ in c.ingest():
            count += 1
            if count >= 3:
                break

        assert c._messages_ingested == 3


class TestEmailConnectorHealthCheck:
    @pytest.mark.asyncio
    async def test_health_check(self, connector_config: EmailConnectorConfig):
        c = EmailConnector(connector_config)
        c._imap = AsyncMock()
        c._imap.is_connected = AsyncMock(return_value=True)
        c._imap.last_uid = "42"

        result = await c.health_check()
        assert result["imap_connected"] is True
        assert result["last_uid"] == "42"
        assert result["imap_host"] == "imap.test.com"
        assert result["imap_mailbox"] == "INBOX"
        assert result["messages_ingested"] == 0


class TestEmailConnectorBackfill:
    @pytest.mark.asyncio
    async def test_backfill_yields_messages(self, connector_config: EmailConnectorConfig):
        c = EmailConnector(connector_config)
        c._imap = AsyncMock()
        c._imap.connect = AsyncMock()
        c._imap.disconnect = AsyncMock()
        c._imap.search_by_date_range = AsyncMock(
            return_value=[_make_fetched("10"), _make_fetched("11")]
        )
        c._s3 = AsyncMock()
        c._s3.start = AsyncMock()
        c._s3.stop = AsyncMock()
        c._s3.upload_raw_eml = AsyncMock(return_value="s3://b/x.eml")

        req = BackfillRequest(
            start=datetime(2025, 1, 1, tzinfo=timezone.utc),
            end=datetime(2025, 1, 31, tzinfo=timezone.utc),
            channel=Channel.EMAIL,
        )
        messages = [m async for m in c.backfill(req)]
        assert len(messages) == 2
        c._imap.search_by_date_range.assert_awaited_once_with(req.start, req.end)

    @pytest.mark.asyncio
    async def test_backfill_cleans_up(self, connector_config: EmailConnectorConfig):
        c = EmailConnector(connector_config)
        c._imap = AsyncMock()
        c._imap.connect = AsyncMock()
        c._imap.disconnect = AsyncMock()
        c._imap.search_by_date_range = AsyncMock(return_value=[])
        c._s3 = AsyncMock()
        c._s3.start = AsyncMock()
        c._s3.stop = AsyncMock()

        req = BackfillRequest(
            start=datetime(2025, 1, 1, tzinfo=timezone.utc),
            end=datetime(2025, 1, 2, tzinfo=timezone.utc),
            channel=Channel.EMAIL,
        )
        _ = [m async for m in c.backfill(req)]
        c._imap.disconnect.assert_awaited_once()
        c._s3.stop.assert_awaited_once()
