"""Authentication endpoints: login, refresh, me."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from umbrella_ui.auth.jwt import create_access_token, create_refresh_token, decode_token
from umbrella_ui.auth.password import verify_password
from umbrella_ui.auth.rbac import get_current_user
from umbrella_ui.auth.schemas import LoginRequest, RefreshRequest, TokenResponse, UserProfile
from umbrella_ui.config import Settings
from umbrella_ui.db.models.iam import GroupRole, Role, User, UserGroup
from umbrella_ui.deps import get_iam_session

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


async def _resolve_roles(user_id: UUID, session: AsyncSession) -> list[str]:
    """Resolve a user's effective roles via: user → user_groups → group_roles → roles."""
    stmt = (
        select(Role.name)
        .join(GroupRole, GroupRole.role_id == Role.id)
        .join(UserGroup, UserGroup.group_id == GroupRole.group_id)
        .where(UserGroup.user_id == user_id)
        .distinct()
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_iam_session)],
):
    """Authenticate with username + password, receive JWT tokens."""
    settings: Settings = request.app.state.settings

    stmt = select(User).where(User.username == body.username)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    roles = await _resolve_roles(user.id, session)
    access_token = create_access_token(user.id, roles, settings)
    refresh_token = create_refresh_token(user.id, settings)

    logger.info("user_login", user_id=str(user.id), username=user.username, roles=roles)

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    body: RefreshRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_iam_session)],
):
    """Exchange a refresh token for a new access + refresh token pair."""
    settings: Settings = request.app.state.settings

    try:
        payload = decode_token(body.refresh_token, settings)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    user_id = UUID(payload["sub"])

    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or deactivated",
        )

    roles = await _resolve_roles(user_id, session)
    access_token = create_access_token(user_id, roles, settings)
    refresh_token = create_refresh_token(user_id, settings)

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.get("/me", response_model=UserProfile)
async def me(
    user: Annotated[dict, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_iam_session)],
):
    """Return the current user's profile and resolved roles."""
    stmt = select(User).where(User.id == user["id"])
    result = await session.execute(stmt)
    db_user = result.scalar_one_or_none()

    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    roles = await _resolve_roles(db_user.id, session)

    return UserProfile(
        id=db_user.id,
        username=db_user.username,
        email=db_user.email,
        is_active=db_user.is_active,
        roles=roles,
    )
