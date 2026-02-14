"""Request/response schemas for IAM endpoints (users, groups, roles)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


# --- Roles -------------------------------------------------------------------

class RoleOut(BaseModel):
    id: UUID
    name: str
    description: str | None
    created_at: datetime


# --- Users -------------------------------------------------------------------

class UserCreate(BaseModel):
    username: str
    email: str
    password: str


class UserUpdate(BaseModel):
    email: str | None = None
    is_active: bool | None = None


class UserOut(BaseModel):
    id: UUID
    username: str
    email: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UserWithRoles(UserOut):
    """User with their resolved roles (for detail views)."""
    roles: list[str]


# --- Groups ------------------------------------------------------------------

class GroupCreate(BaseModel):
    name: str
    description: str | None = None


class GroupUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class GroupOut(BaseModel):
    id: UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime


class GroupDetail(GroupOut):
    """Group with its roles and member count."""
    roles: list[str]
    member_count: int


# --- Membership & Assignment -------------------------------------------------

class AddUserToGroup(BaseModel):
    group_id: UUID


class AssignRoleToGroup(BaseModel):
    role_id: UUID
