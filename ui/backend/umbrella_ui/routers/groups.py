"""Group CRUD endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from umbrella_ui.auth.rbac import require_role
from umbrella_ui.db.models.iam import Group, GroupRole, Role, User, UserGroup
from umbrella_ui.deps import get_iam_session
from umbrella_ui.schemas.common import PaginatedResponse
from umbrella_ui.schemas.iam import AssignRoleToGroup, GroupCreate, GroupDetail, GroupOut, GroupUpdate, UserOut

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1/groups", tags=["groups"])


async def _group_detail(group: Group, session: AsyncSession) -> GroupDetail:
    # Get role names
    stmt = (
        select(Role.name)
        .join(GroupRole, GroupRole.role_id == Role.id)
        .where(GroupRole.group_id == group.id)
    )
    result = await session.execute(stmt)
    roles = list(result.scalars().all())

    # Count members
    count_result = await session.execute(
        select(func.count()).select_from(UserGroup).where(UserGroup.group_id == group.id)
    )
    member_count = count_result.scalar_one()

    return GroupDetail(
        id=group.id,
        name=group.name,
        description=group.description,
        created_at=group.created_at,
        updated_at=group.updated_at,
        roles=roles,
        member_count=member_count,
    )


@router.get("", response_model=PaginatedResponse[GroupDetail])
async def list_groups(
    session: Annotated[AsyncSession, Depends(get_iam_session)],
    _user: Annotated[dict, Depends(require_role("admin"))],
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
):
    total_result = await session.execute(select(func.count()).select_from(Group))
    total = total_result.scalar_one()

    result = await session.execute(select(Group).offset(offset).limit(limit))
    groups = result.scalars().all()

    items = [await _group_detail(g, session) for g in groups]
    return PaginatedResponse(items=items, total=total, offset=offset, limit=limit)


@router.post("", response_model=GroupOut, status_code=status.HTTP_201_CREATED)
async def create_group(
    body: GroupCreate,
    session: Annotated[AsyncSession, Depends(get_iam_session)],
    _user: Annotated[dict, Depends(require_role("admin"))],
):
    group = Group(name=body.name, description=body.description)
    session.add(group)
    try:
        await session.commit()
        await session.refresh(group)
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Group name already exists")

    return GroupOut.model_validate(group, from_attributes=True)


@router.get("/{group_id}", response_model=GroupDetail)
async def get_group(
    group_id: UUID,
    session: Annotated[AsyncSession, Depends(get_iam_session)],
    _user: Annotated[dict, Depends(require_role("admin"))],
):
    result = await session.execute(select(Group).where(Group.id == group_id))
    group = result.scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=404, detail="Group not found")
    return await _group_detail(group, session)


@router.patch("/{group_id}", response_model=GroupOut)
async def update_group(
    group_id: UUID,
    body: GroupUpdate,
    session: Annotated[AsyncSession, Depends(get_iam_session)],
    _user: Annotated[dict, Depends(require_role("admin"))],
):
    result = await session.execute(select(Group).where(Group.id == group_id))
    group = result.scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=404, detail="Group not found")

    if body.name is not None:
        group.name = body.name
    if body.description is not None:
        group.description = body.description

    await session.commit()
    await session.refresh(group)
    return GroupOut.model_validate(group, from_attributes=True)


@router.get("/{group_id}/members", response_model=list[UserOut])
async def list_group_members(
    group_id: UUID,
    session: Annotated[AsyncSession, Depends(get_iam_session)],
    _user: Annotated[dict, Depends(require_role("admin"))],
):
    result = await session.execute(select(Group).where(Group.id == group_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Group not found")

    stmt = (
        select(User)
        .join(UserGroup, UserGroup.user_id == User.id)
        .where(UserGroup.group_id == group_id)
    )
    result = await session.execute(stmt)
    users = result.scalars().all()
    return [UserOut.model_validate(u, from_attributes=True) for u in users]


@router.post("/{group_id}/roles", status_code=status.HTTP_200_OK)
async def assign_role_to_group(
    group_id: UUID,
    body: AssignRoleToGroup,
    session: Annotated[AsyncSession, Depends(get_iam_session)],
    current_user: Annotated[dict, Depends(require_role("admin"))],
):
    result = await session.execute(select(Group).where(Group.id == group_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Group not found")

    result = await session.execute(select(Role).where(Role.id == body.role_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Role not found")

    gr = GroupRole(
        group_id=group_id,
        role_id=body.role_id,
        assigned_by=current_user["id"],
    )
    session.add(gr)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Role already assigned to group")

    return {"ok": True}


@router.delete("/{group_id}/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_role_from_group(
    group_id: UUID,
    role_id: UUID,
    session: Annotated[AsyncSession, Depends(get_iam_session)],
    _user: Annotated[dict, Depends(require_role("admin"))],
):
    await session.execute(
        delete(GroupRole).where(
            GroupRole.group_id == group_id,
            GroupRole.role_id == role_id,
        )
    )
    await session.commit()
