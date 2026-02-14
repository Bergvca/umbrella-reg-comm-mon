"""Roles endpoints (read-only)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from umbrella_ui.auth.rbac import require_role
from umbrella_ui.db.models.iam import Role
from umbrella_ui.deps import get_iam_session
from umbrella_ui.schemas.iam import RoleOut

router = APIRouter(prefix="/api/v1/roles", tags=["roles"])


@router.get("", response_model=list[RoleOut])
async def list_roles(
    session: Annotated[AsyncSession, Depends(get_iam_session)],
    _user: Annotated[dict, Depends(require_role("reviewer"))],
):
    result = await session.execute(select(Role))
    roles = result.scalars().all()
    return [RoleOut.model_validate(r, from_attributes=True) for r in roles]
