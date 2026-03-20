"""Request/response schemas for entity endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# ── Handles ──────────────────────────────────────────────


class HandleCreate(BaseModel):
    handle_type: str
    handle_value: str
    is_primary: bool = False


class HandleOut(BaseModel):
    id: UUID
    entity_id: UUID
    handle_type: str
    handle_value: str
    is_primary: bool
    created_at: datetime


# ── Attributes ───────────────────────────────────────────


class AttributeCreate(BaseModel):
    attr_key: str
    attr_value: str
    valid_from: datetime | None = None
    valid_to: datetime | None = None


class AttributeOut(BaseModel):
    id: UUID
    entity_id: UUID
    attr_key: str
    attr_value: str
    valid_from: datetime | None
    valid_to: datetime | None
    created_at: datetime


# ── Entities ─────────────────────────────────────────────


class EntityCreate(BaseModel):
    display_name: str
    entity_type: str
    handles: list[HandleCreate] = Field(default_factory=list)
    attributes: list[AttributeCreate] = Field(default_factory=list)


class EntityUpdate(BaseModel):
    display_name: str | None = None
    entity_type: str | None = None


class EntityOut(BaseModel):
    id: UUID
    display_name: str
    entity_type: str
    created_at: datetime
    updated_at: datetime
    created_by: UUID | None
    handles: list[HandleOut] = Field(default_factory=list)
    attributes: list[AttributeOut] = Field(default_factory=list)


# ── Batch ────────────────────────────────────────────────


class BatchEntityItem(BaseModel):
    display_name: str
    entity_type: str
    handles: list[HandleCreate] = Field(default_factory=list)
    attributes: list[AttributeCreate] = Field(default_factory=list)


class BatchUploadResult(BaseModel):
    created: int
    updated: int
    errors: list[str] = Field(default_factory=list)
