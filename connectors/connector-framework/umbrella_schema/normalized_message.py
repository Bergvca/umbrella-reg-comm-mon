"""Normalized message schema — the canonical data model shared across all Umbrella services."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Channel(str, Enum):
    """Communication channel that produced the message."""

    TEAMS_CHAT = "teams_chat"
    TEAMS_CALLS = "teams_calls"
    UNIGY_TURRET = "unigy_turret"
    BLOOMBERG_CHAT = "bloomberg_chat"
    BLOOMBERG_EMAIL = "bloomberg_email"
    EMAIL = "email"


class Direction(str, Enum):
    """Direction of the communication relative to the monitored entity."""

    INBOUND = "inbound"
    OUTBOUND = "outbound"
    INTERNAL = "internal"


class Participant(BaseModel):
    """A party involved in the communication."""

    id: str = Field(description="Unique identifier for the participant (e.g. email, user ID)")
    name: str = Field(description="Display name")
    role: str = Field(description="Role in the conversation (e.g. sender, recipient, participant)")


class Attachment(BaseModel):
    """A file attached to the communication."""

    name: str = Field(description="Original filename")
    content_type: str = Field(description="MIME type (e.g. application/pdf)")
    s3_uri: str = Field(description="S3 URI where the attachment is stored")


class NormalizedMessage(BaseModel):
    """Canonical message format produced by the ingestion API.

    Every communication — regardless of source channel — is normalized
    into this schema before being published to Kafka and persisted to S3.
    """

    message_id: str = Field(description="Globally unique message identifier")
    channel: Channel = Field(description="Source communication channel")
    direction: Direction = Field(description="Inbound, outbound, or internal")
    timestamp: datetime = Field(description="When the communication occurred (UTC, ISO-8601)")
    participants: list[Participant] = Field(
        min_length=1,
        description="Parties involved in the communication",
    )
    body_text: str | None = Field(
        default=None,
        description="Text content of the message (null for audio-only)",
    )
    audio_ref: str | None = Field(
        default=None,
        description="S3 URI of the audio recording (null for text-only)",
    )
    attachments: list[Attachment] = Field(
        default_factory=list,
        description="Files attached to the communication",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Channel-specific fields not covered by the canonical schema",
    )
