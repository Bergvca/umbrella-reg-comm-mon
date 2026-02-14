"""Request/response schemas for review endpoints (queues, decisions, audit)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


# --- Decision statuses ---

class DecisionStatusOut(BaseModel):
    id: UUID
    name: str
    description: str | None
    is_terminal: bool
    display_order: int
    created_at: datetime


# --- Decisions ---

class DecisionCreate(BaseModel):
    status_id: UUID
    comment: str | None = None


class DecisionOut(BaseModel):
    id: UUID
    alert_id: UUID
    reviewer_id: UUID
    status_id: UUID
    status_name: str | None = None
    comment: str | None
    decided_at: datetime


# --- Queues ---

class QueueCreate(BaseModel):
    name: str
    description: str | None = None
    policy_id: UUID


class QueueOut(BaseModel):
    id: UUID
    name: str
    description: str | None
    policy_id: UUID
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime


class QueueDetail(QueueOut):
    batch_count: int
    total_items: int


# --- Batches ---

class BatchCreate(BaseModel):
    name: str | None = None


class BatchAssign(BaseModel):
    assigned_to: UUID


class BatchStatusUpdate(BaseModel):
    status: str  # "pending", "in_progress", "completed"


class BatchOut(BaseModel):
    id: UUID
    queue_id: UUID
    name: str | None
    assigned_to: UUID | None
    assigned_by: UUID | None
    assigned_at: datetime | None
    status: str
    created_at: datetime
    updated_at: datetime
    item_count: int = 0


# --- Queue items ---

class QueueItemCreate(BaseModel):
    alert_id: UUID
    position: int


class QueueItemOut(BaseModel):
    id: UUID
    batch_id: UUID
    alert_id: UUID
    position: int
    created_at: datetime


# --- Audit log ---

class AuditLogEntry(BaseModel):
    id: UUID
    decision_id: UUID
    actor_id: UUID | None
    action: str
    old_values: dict | None
    new_values: dict | None
    occurred_at: datetime
    ip_address: str | None
    user_agent: str | None
