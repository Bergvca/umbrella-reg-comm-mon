"""Tests for the deterministic event ID generator."""

from __future__ import annotations

import hashlib
import textwrap
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from umbrella_ingestion.event_id import EventIdGenerator
from umbrella_schema.normalized_message import (
    Channel,
    Direction,
    NormalizedMessage,
    Participant,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_msg(
    *,
    channel: Channel = Channel.EMAIL,
    message_id: str = "test-id",
    body_text: str = "hello world",
    timestamp: datetime = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc),
    participants: list[Participant] | None = None,
    metadata: dict | None = None,
) -> NormalizedMessage:
    if participants is None:
        participants = [
            Participant(id="alice@example.com", name="Alice", role="sender"),
            Participant(id="bob@example.com", name="Bob", role="recipient"),
        ]
    return NormalizedMessage(
        message_id=message_id,
        channel=channel,
        direction=Direction.OUTBOUND,
        timestamp=timestamp,
        participants=participants,
        body_text=body_text,
        metadata=metadata or {},
    )


def _write_config(tmp_path: Path, config: dict) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    p = tmp_path / "event_id.yml"
    p.write_text(yaml.dump(config))
    return p


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDeterminism:
    """Same inputs must always produce the same event ID."""

    def test_same_message_same_id(self, tmp_path: Path) -> None:
        cfg = _write_config(tmp_path, {"default": ["channel", "timestamp", "body_text"]})
        gen = EventIdGenerator(cfg)
        msg = _make_msg()
        assert gen.generate(msg) == gen.generate(msg)

    def test_participant_order_irrelevant(self, tmp_path: Path) -> None:
        """Participants are sorted by id, so order shouldn't matter."""
        cfg = _write_config(tmp_path, {"default": ["participants"]})
        gen = EventIdGenerator(cfg)

        msg_a = _make_msg(participants=[
            Participant(id="alice@example.com", name="Alice", role="sender"),
            Participant(id="bob@example.com", name="Bob", role="recipient"),
        ])
        msg_b = _make_msg(participants=[
            Participant(id="bob@example.com", name="Bob", role="recipient"),
            Participant(id="alice@example.com", name="Alice", role="sender"),
        ])
        assert gen.generate(msg_a) == gen.generate(msg_b)


class TestDifferentiation:
    """Different content must produce different IDs."""

    def test_different_body(self, tmp_path: Path) -> None:
        cfg = _write_config(tmp_path, {"default": ["body_text"]})
        gen = EventIdGenerator(cfg)
        msg_a = _make_msg(body_text="hello")
        msg_b = _make_msg(body_text="goodbye")
        assert gen.generate(msg_a) != gen.generate(msg_b)

    def test_different_timestamp(self, tmp_path: Path) -> None:
        cfg = _write_config(tmp_path, {"default": ["timestamp"]})
        gen = EventIdGenerator(cfg)
        msg_a = _make_msg(timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc))
        msg_b = _make_msg(timestamp=datetime(2026, 6, 1, tzinfo=timezone.utc))
        assert gen.generate(msg_a) != gen.generate(msg_b)

    def test_different_channel(self, tmp_path: Path) -> None:
        cfg = _write_config(tmp_path, {"default": ["channel"]})
        gen = EventIdGenerator(cfg)
        msg_a = _make_msg(channel=Channel.EMAIL)
        msg_b = _make_msg(channel=Channel.TEAMS_CHAT)
        assert gen.generate(msg_a) != gen.generate(msg_b)


class TestChannelConfig:
    """Channel-specific field lists should be used when available."""

    def test_uses_channel_specific_fields(self, tmp_path: Path) -> None:
        cfg = _write_config(tmp_path, {
            "default": ["body_text"],
            "email": ["channel", "body_text"],
        })
        gen = EventIdGenerator(cfg)
        msg = _make_msg(channel=Channel.EMAIL)

        # Email config includes channel, so changing channel would change the hash.
        # With default (body_text only), channel is ignored.
        gen_default_only = EventIdGenerator(
            _write_config(tmp_path / "sub", {"default": ["body_text"]})
        )

        # The two generators should produce different IDs since they hash different fields
        assert gen.generate(msg) != gen_default_only.generate(msg)

    def test_falls_back_to_default(self, tmp_path: Path) -> None:
        cfg = _write_config(tmp_path, {"default": ["body_text"]})
        gen = EventIdGenerator(cfg)
        msg = _make_msg(channel=Channel.TEAMS_CHAT)
        # Should not raise — falls back to default
        result = gen.generate(msg)
        assert isinstance(result, str) and len(result) == 64


class TestMetadotPath:
    """Dot-notation paths into metadata should resolve correctly."""

    def test_metadata_field(self, tmp_path: Path) -> None:
        cfg = _write_config(tmp_path, {
            "default": ["body_text"],
            "email": ["metadata.raw_message_id", "body_text"],
        })
        gen = EventIdGenerator(cfg)

        msg_a = _make_msg(metadata={"raw_message_id": "<abc@example.com>"})
        msg_b = _make_msg(metadata={"raw_message_id": "<def@example.com>"})
        assert gen.generate(msg_a) != gen.generate(msg_b)

    def test_missing_metadata_field(self, tmp_path: Path) -> None:
        cfg = _write_config(tmp_path, {
            "default": ["body_text"],
            "email": ["metadata.raw_message_id", "body_text"],
        })
        gen = EventIdGenerator(cfg)
        msg = _make_msg(metadata={})
        # Missing field resolves to empty string — should not raise
        result = gen.generate(msg)
        assert isinstance(result, str) and len(result) == 64


class TestNullBody:
    """body_text can be None for audio-only messages."""

    def test_none_body_text(self, tmp_path: Path) -> None:
        cfg = _write_config(tmp_path, {"default": ["body_text"]})
        gen = EventIdGenerator(cfg)
        msg = _make_msg(body_text=None)
        result = gen.generate(msg)
        assert isinstance(result, str) and len(result) == 64


class TestConfigValidation:
    """Config must have a 'default' key."""

    def test_missing_default_raises(self, tmp_path: Path) -> None:
        cfg = _write_config(tmp_path, {"email": ["body_text"]})
        with pytest.raises(ValueError, match="default"):
            EventIdGenerator(cfg)


class TestDefaultConfigLoads:
    """The shipped event_id.yml should load without error."""

    def test_load_default_config(self) -> None:
        gen = EventIdGenerator()
        msg = _make_msg(metadata={"raw_message_id": "<test@example.com>"})
        result = gen.generate(msg)
        assert isinstance(result, str) and len(result) == 64
