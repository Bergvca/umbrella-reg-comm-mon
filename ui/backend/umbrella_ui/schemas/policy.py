"""Request/response schemas for policy management endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


# --- Risk models ---

class RiskModelCreate(BaseModel):
    name: str
    description: str | None = None


class RiskModelUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None


class RiskModelOut(BaseModel):
    id: UUID
    name: str
    description: str | None
    is_active: bool
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime


class RiskModelDetail(RiskModelOut):
    policy_count: int


# --- Policies ---

class PolicyCreate(BaseModel):
    risk_model_id: UUID
    name: str
    description: str | None = None


class PolicyUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None


class PolicyOut(BaseModel):
    id: UUID
    risk_model_id: UUID
    name: str
    description: str | None
    is_active: bool
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime


class PolicyDetail(PolicyOut):
    risk_model_name: str
    rule_count: int
    group_count: int


# --- Rules ---

class RuleCreate(BaseModel):
    name: str
    description: str | None = None
    kql: str
    severity: Literal["low", "medium", "high", "critical"]


class RuleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    kql: str | None = None
    severity: Literal["low", "medium", "high", "critical"] | None = None
    is_active: bool | None = None


class RuleOut(BaseModel):
    id: UUID
    policy_id: UUID
    name: str
    description: str | None
    kql: str
    severity: str
    is_active: bool
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime


# --- Group-policy assignment ---

class AssignGroupPolicy(BaseModel):
    group_id: UUID


class GroupPolicyOut(BaseModel):
    group_id: UUID
    policy_id: UUID
    assigned_by: UUID | None
    assigned_at: datetime
