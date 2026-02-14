"""FastAPI dependencies for authentication and role-based access control."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

import structlog
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError

from umbrella_ui.auth.jwt import decode_token
from umbrella_ui.config import Settings

logger = structlog.get_logger()

_bearer_scheme = HTTPBearer()


def _get_settings(request: Request) -> Settings:
    return request.app.state.settings


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer_scheme)],
    settings: Annotated[Settings, Depends(_get_settings)],
) -> dict:
    """Decode JWT and return ``{"id": UUID, "roles": [...]}``."""
    try:
        payload = decode_token(credentials.credentials, settings)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    return {
        "id": UUID(payload["sub"]),
        "roles": payload.get("roles", []),
    }


def require_role(*allowed_roles: str):
    """Return a FastAPI dependency that checks the user has at least one of the given roles.

    Role hierarchy:
        - ``admin`` implies ``supervisor`` and ``reviewer``
        - ``supervisor`` implies ``reviewer``
    """
    # Maps required role → set of user roles that satisfy it.
    # "reviewer" can be fulfilled by admin, supervisor, or reviewer.
    HIERARCHY = {
        "reviewer": {"admin", "supervisor", "reviewer"},
        "supervisor": {"admin", "supervisor"},
        "admin": {"admin"},
    }
    expanded = set()
    for role in allowed_roles:
        expanded.update(HIERARCHY.get(role, {role}))

    async def _check(user: dict = Depends(get_current_user)) -> dict:
        user_roles = set(user.get("roles", []))
        if not user_roles & expanded:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user

    return _check
