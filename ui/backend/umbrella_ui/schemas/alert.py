"""Request/response schemas for alert endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, model_validator

from umbrella_ui.es.models import ESMessage


class AlertOut(BaseModel):
    """Alert metadata from PostgreSQL."""

    id: UUID
    name: str
    rule_id: UUID
    rule_name: str | None = None
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


class GenerationJobCreate(BaseModel):
    """Request body for POST /alert-generation/jobs."""

    scope_type: Literal["all", "policies", "risk_models"]
    scope_ids: list[UUID] | None = None
    query_kql: str | None = None

    @model_validator(mode="after")
    def check_scope_ids(self) -> "GenerationJobCreate":
        if self.scope_type != "all" and not self.scope_ids:
            raise ValueError("scope_ids is required when scope_type is not 'all'")
        return self


class GenerationJobOut(BaseModel):
    """Response schema for a generation job."""

    model_config = {"from_attributes": True}

    id: UUID
    scope_type: str
    scope_ids: list[UUID] | None
    query_kql: str | None
    query_kql_resolved: str | None
    status: str
    alerts_created: int
    rules_evaluated: int
    documents_scanned: int
    error_message: str | None
    created_by: UUID
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
