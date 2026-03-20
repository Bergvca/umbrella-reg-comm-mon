"""Deterministic event ID generation via SHA-256 hashing of configurable fields."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import structlog
import yaml

from umbrella_schema.normalized_message import NormalizedMessage

logger = structlog.get_logger()

_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "event_id_config.yml"


class EventIdGenerator:
    """Generate deterministic event IDs by hashing configured fields of a NormalizedMessage."""

    def __init__(self, config_path: Path = _DEFAULT_CONFIG_PATH) -> None:
        self._field_map: dict[str, list[str]] = self._load_config(config_path)

    @staticmethod
    def _load_config(config_path: Path) -> dict[str, list[str]]:
        with open(config_path) as f:
            raw = yaml.safe_load(f)
        if not isinstance(raw, dict) or "default" not in raw:
            raise ValueError(f"event_id config must have a 'default' key: {config_path}")
        return raw

    def generate(self, msg: NormalizedMessage) -> str:
        """Return a hex SHA-256 digest computed from the configured fields for the message channel."""
        channel_key = msg.channel.value.lower()
        fields = self._field_map.get(channel_key, self._field_map["default"])

        parts: list[str] = []
        for dot_path in fields:
            parts.append(self._resolve_field(msg, dot_path))

        payload = "\n".join(parts)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _resolve_field(msg: NormalizedMessage, dot_path: str) -> str:
        """Resolve a dot-notation path on a NormalizedMessage to a stable string representation."""
        segments = dot_path.split(".")
        current: Any = msg

        for seg in segments:
            if isinstance(current, dict):
                current = current.get(seg)
            elif hasattr(current, seg):
                current = getattr(current, seg)
            else:
                current = None
            if current is None:
                return ""

        return _serialize_value(current)


def _serialize_value(value: Any) -> str:
    """Convert a field value to a deterministic string for hashing."""
    if isinstance(value, list):
        # Participants: sort by id for determinism, then serialize each
        items = []
        for item in value:
            if hasattr(item, "id"):
                items.append((item.id, _serialize_participant(item)))
            else:
                items.append((str(item), str(item)))
        items.sort(key=lambda x: x[0])
        return "|".join(v for _, v in items)

    if hasattr(value, "isoformat"):
        return value.isoformat()

    if hasattr(value, "value"):
        # Enum
        return value.value

    return str(value) if value is not None else ""


def _serialize_participant(p: Any) -> str:
    return f"{p.id}:{p.role}"
