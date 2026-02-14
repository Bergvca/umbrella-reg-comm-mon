"""Request/response schemas for alert endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from umbrella_ui.es.models import ESMessage


class AlertOut(BaseModel):
    """Alert metadata from PostgreSQL."""

    id: UUID
    name: str
    rule_id: UUID
    es_index: str
    es_document_id: str
    es_document_ts: datetime | None
    severity: str
    status: str
    created_at: datetime


class AlertWithMessage(AlertOut):
    """Alert metadata merged with the linked ES message (for detail view)."""

    rule_name: str | None = None
    policy_name: str | None = None
    message: ESMessage | None = None


class AlertStatusUpdate(BaseModel):
    """Request body for PATCH /alerts/{id}/status."""

    status: str  # "open", "in_review", or "closed"


class AlertListParams(BaseModel):
    """Query parameters for GET /alerts."""

    severity: str | None = None
    status: str | None = None
    channel: str | None = None
    rule_id: UUID | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    offset: int = 0
    limit: int = 50
