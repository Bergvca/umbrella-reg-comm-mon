"""Tests for umbrella_connector.models."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from umbrella_connector.models import (
    BackfillRequest,
    ConnectorStatus,
    DeadLetterEnvelope,
    HealthStatus,
    RawMessage,
)
from umbrella_schema import Channel


class TestRawMessage:
    def test_minimal_construction(self):
        msg = RawMessage(
            raw_message_id="id-1",
            channel=Channel.TEAMS_CHAT,
            raw_payload={"key": "value"},
        )
        assert msg.raw_message_id == "id-1"
        assert msg.channel == Channel.TEAMS_CHAT
        assert msg.raw_payload == {"key": "value"}

    def test_defaults(self):
        msg = RawMessage(
            raw_message_id="id-2",
            channel=Channel.EMAIL,
            raw_payload={},
        )
        assert msg.raw_format == "json"
        assert msg.attachment_refs == []
        assert msg.metadata == {}
        assert isinstance(msg.ingested_at, datetime)

    def test_full_construction(self):
        ts = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        msg = RawMessage(
            raw_message_id="id-3",
            channel=Channel.BLOOMBERG_CHAT,
            raw_payload={"body": "hello"},
            raw_format="xml",
            attachment_refs=["s3://bucket/a.pdf", "s3://bucket/b.docx"],
            metadata={"source": "bloomberg"},
            ingested_at=ts,
        )
        assert msg.raw_format == "xml"
        assert len(msg.attachment_refs) == 2
        assert msg.ingested_at == ts

    def test_missing_required_fields(self):
        with pytest.raises(ValidationError):
            RawMessage(raw_message_id="id-4", channel=Channel.EMAIL)  # type: ignore[call-arg]

    def test_serialization_roundtrip(self, raw_message: RawMessage):
        json_str = raw_message.model_dump_json()
        restored = RawMessage.model_validate_json(json_str)
        assert restored.raw_message_id == raw_message.raw_message_id
        assert restored.channel == raw_message.channel
        assert restored.raw_payload == raw_message.raw_payload

    def test_all_channels(self):
        for ch in Channel:
            msg = RawMessage(
                raw_message_id=f"ch-{ch.value}",
                channel=ch,
                raw_payload={},
            )
            assert msg.channel == ch


class TestHealthStatus:
    def test_construction(self):
        hs = HealthStatus(
            connector_name="test",
            status=ConnectorStatus.RUNNING,
            uptime_seconds=42.5,
        )
        assert hs.connector_name == "test"
        assert hs.status == ConnectorStatus.RUNNING
        assert hs.uptime_seconds == 42.5
        assert hs.details == {}

    def test_with_details(self):
        hs = HealthStatus(
            connector_name="test",
            status=ConnectorStatus.DEGRADED,
            uptime_seconds=100.0,
            details={"last_poll": "2025-01-01T00:00:00Z", "queue_depth": 5},
        )
        assert hs.details["queue_depth"] == 5

    def test_serialization(self):
        hs = HealthStatus(
            connector_name="test",
            status=ConnectorStatus.STARTING,
            uptime_seconds=0.1,
        )
        data = hs.model_dump(mode="json")
        assert data["status"] == "starting"


class TestBackfillRequest:
    def test_construction(self):
        req = BackfillRequest(
            start=datetime(2025, 1, 1, tzinfo=timezone.utc),
            end=datetime(2025, 1, 31, tzinfo=timezone.utc),
            channel=Channel.UNIGY_TURRET,
        )
        assert req.channel == Channel.UNIGY_TURRET
        assert req.params == {}

    def test_with_params(self):
        req = BackfillRequest(
            start=datetime(2025, 1, 1, tzinfo=timezone.utc),
            end=datetime(2025, 1, 2, tzinfo=timezone.utc),
            channel=Channel.EMAIL,
            params={"mailbox": "compliance@example.com"},
        )
        assert req.params["mailbox"] == "compliance@example.com"

    def test_missing_required(self):
        with pytest.raises(ValidationError):
            BackfillRequest(start=datetime.now(tz=timezone.utc))  # type: ignore[call-arg]


class TestDeadLetterEnvelope:
    def test_construction(self, raw_message: RawMessage):
        env = DeadLetterEnvelope(
            original_message=raw_message,
            connector_name="teams-chat",
            error="Connection refused",
            attempts=5,
        )
        assert env.original_message.raw_message_id == "msg-001"
        assert env.connector_name == "teams-chat"
        assert env.error == "Connection refused"
        assert env.attempts == 5
        assert isinstance(env.failed_at, datetime)

    def test_serialization_roundtrip(self, raw_message: RawMessage):
        env = DeadLetterEnvelope(
            original_message=raw_message,
            connector_name="email",
            error="timeout",
            attempts=3,
        )
        json_str = env.model_dump_json()
        restored = DeadLetterEnvelope.model_validate_json(json_str)
        assert restored.original_message.raw_message_id == raw_message.raw_message_id
        assert restored.error == "timeout"


class TestConnectorStatus:
    def test_all_values(self):
        assert ConnectorStatus.STARTING == "starting"
        assert ConnectorStatus.RUNNING == "running"
        assert ConnectorStatus.DEGRADED == "degraded"
        assert ConnectorStatus.STOPPING == "stopping"
        assert ConnectorStatus.STOPPED == "stopped"

    def test_is_str_enum(self):
        assert isinstance(ConnectorStatus.RUNNING, str)
