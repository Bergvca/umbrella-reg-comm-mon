"""Request/response schemas for authentication endpoints."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserProfile(BaseModel):
    """Returned by GET /auth/me."""

    id: UUID
    username: str
    email: str
    is_active: bool
    roles: list[str]
