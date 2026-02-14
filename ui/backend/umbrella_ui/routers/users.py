"""User CRUD endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from umbrella_ui.auth.password import hash_password
from umbrella_ui.auth.rbac import get_current_user, require_role
from umbrella_ui.db.models.iam import Group, GroupRole, Role, User, UserGroup
from umbrella_ui.deps import get_iam_session
from umbrella_ui.routers.auth import _resolve_roles
from umbrella_ui.schemas.common import PaginatedResponse
from umbrella_ui.schemas.iam import AddUserToGroup, GroupOut, UserCreate, UserOut, UserUpdate, UserWithRoles

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.get("", response_model=PaginatedResponse[UserOut])
async def list_users(
    session: Annotated[AsyncSession, Depends(get_iam_session)],
    _user: Annotated[dict, Depends(require_role("admin"))],
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
):
    total_result = await session.execute(select(func.count()).select_from(User))
    total = total_result.scalar_one()

    result = await session.execute(select(User).offset(offset).limit(limit))
    users = result.scalars().all()

    return PaginatedResponse(
        items=[UserOut.model_validate(u, from_attributes=True) for u in users],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreate,
    session: Annotated[AsyncSession, Depends(get_iam_session)],
    _user: Annotated[dict, Depends(require_role("admin"))],
):
    user = User(
        username=body.username,
        email=body.email,
        password_hash=hash_password(body.password),
    )
    session.add(user)
    try:
        await session.commit()
        await session.refresh(user)
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Username or email already exists")

    return UserOut.model_validate(user, from_attributes=True)


@router.get("/{user_id}", response_model=UserWithRoles)
async def get_user(
    user_id: UUID,
    session: Annotated[AsyncSession, Depends(get_iam_session)],
    _user: Annotated[dict, Depends(require_role("admin"))],
):
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    roles = await _resolve_roles(user_id, session)
    return UserWithRoles(
        id=user.id,
        username=user.username,
        email=user.email,
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
        roles=roles,
    )


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: UUID,
    body: UserUpdate,
    session: Annotated[AsyncSession, Depends(get_iam_session)],
    _user: Annotated[dict, Depends(require_role("admin"))],
):
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if body.email is not None:
        user.email = body.email
    if body.is_active is not None:
        user.is_active = body.is_active

    await session.execute(
        text("UPDATE iam.users SET updated_at = now() WHERE id = :id"),
        {"id": user_id},
    )
    await session.commit()
    await session.refresh(user)

    return UserOut.model_validate(user, from_attributes=True)


@router.get("/{user_id}/groups", response_model=list[GroupOut])
async def list_user_groups(
    user_id: UUID,
    session: Annotated[AsyncSession, Depends(get_iam_session)],
    _user: Annotated[dict, Depends(require_role("admin"))],
):
    result = await session.execute(select(User).where(User.id == user_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="User not found")

    stmt = (
        select(Group)
        .join(UserGroup, UserGroup.group_id == Group.id)
        .where(UserGroup.user_id == user_id)
    )
    result = await session.execute(stmt)
    groups = result.scalars().all()
    return [GroupOut.model_validate(g, from_attributes=True) for g in groups]


@router.post("/{user_id}/groups", status_code=status.HTTP_200_OK)
async def add_user_to_group(
    user_id: UUID,
    body: AddUserToGroup,
    session: Annotated[AsyncSession, Depends(get_iam_session)],
    current_user: Annotated[dict, Depends(require_role("admin"))],
):
    result = await session.execute(select(User).where(User.id == user_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="User not found")

    result = await session.execute(select(Group).where(Group.id == body.group_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Group not found")

    ug = UserGroup(
        user_id=user_id,
        group_id=body.group_id,
        assigned_by=current_user["id"],
    )
    session.add(ug)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="User already in group")

    return {"ok": True}


@router.delete("/{user_id}/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_user_from_group(
    user_id: UUID,
    group_id: UUID,
    session: Annotated[AsyncSession, Depends(get_iam_session)],
    _user: Annotated[dict, Depends(require_role("admin"))],
):
    await session.execute(
        delete(UserGroup).where(
            UserGroup.user_id == user_id,
            UserGroup.group_id == group_id,
        )
    )
    await session.commit()
