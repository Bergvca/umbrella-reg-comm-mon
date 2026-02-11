"""Data models for the connector plugin framework."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from umbrella_schema import Channel


class ConnectorStatus(str, Enum):
    """Runtime status of a connector instance."""

    STARTING = "starting"
    RUNNING = "running"
    DEGRADED = "degraded"
    STOPPING = "stopping"
    STOPPED = "stopped"


class RawMessage(BaseModel):
    """Envelope for raw payloads before normalization.

    Connectors yield RawMessage instances from their ingest/backfill
    generators.  The framework delivers them to the ingestion API
    (or Kafka) and handles retry / dead-letter on failure.
    """

    raw_message_id: str = Field(description="Unique identifier for this raw message")
    channel: Channel = Field(description="Source communication channel")
    raw_payload: dict[str, Any] = Field(description="Raw payload from the source system")
    raw_format: str = Field(
        default="json",
        description="Hint for the ingestion API parser (e.g. json, xml, mime)",
    )
    attachment_refs: list[str] = Field(
        default_factory=list,
        description="S3 URIs of binaries already uploaded by the connector",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Connector-specific metadata (correlation IDs, source timestamps, etc.)",
    )
    ingested_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp when the connector captured this message (UTC)",
    )


class HealthStatus(BaseModel):
    """Response model for the /health and /ready K8s probe endpoints."""

    connector_name: str = Field(description="Name of the connector")
    status: ConnectorStatus = Field(description="Current connector status")
    uptime_seconds: float = Field(description="Seconds since the connector started")
    details: dict[str, Any] = Field(
        default_factory=dict,
        description="Connector-specific health details (e.g. last poll time, queue depth)",
    )


class BackfillRequest(BaseModel):
    """Parameters for a historical backfill operation."""

    start: datetime = Field(description="Start of the backfill window (UTC)")
    end: datetime = Field(description="End of the backfill window (UTC)")
    channel: Channel = Field(description="Channel to backfill")
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Connector-specific backfill parameters",
    )


class DeadLetterEnvelope(BaseModel):
    """Wrapper for messages that failed delivery after retry exhaustion."""

    original_message: RawMessage = Field(description="The message that could not be delivered")
    connector_name: str = Field(description="Connector that produced the message")
    error: str = Field(description="Final error message")
    attempts: int = Field(description="Total delivery attempts made")
    failed_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp when the message was routed to dead-letter (UTC)",
    )
