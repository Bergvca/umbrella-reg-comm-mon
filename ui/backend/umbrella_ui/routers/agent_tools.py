"""Agent tool registry endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from umbrella_ui.auth.rbac import require_role
from umbrella_ui.db.models.agent import AgentTool
from umbrella_ui.deps import get_agent_session
from umbrella_ui.schemas.agent import ToolOut
from umbrella_ui.schemas.common import PaginatedResponse

router = APIRouter(prefix="/api/v1/agent-tools", tags=["agent-tools"])


@router.get("", response_model=PaginatedResponse[ToolOut])
async def list_tools(
    session: Annotated[AsyncSession, Depends(get_agent_session)],
    _user: Annotated[dict, Depends(require_role("supervisor"))],
    category: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
):
    base = select(AgentTool).where(AgentTool.is_active.is_(True))
    if category:
        base = base.where(AgentTool.category == category)

    total = (await session.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    stmt = base.offset(offset).limit(limit).order_by(AgentTool.name)
    rows = (await session.execute(stmt)).scalars().all()

    return PaginatedResponse(
        items=[
            ToolOut(
                id=t.id,
                name=t.name,
                display_name=t.display_name,
                description=t.description,
                category=t.category,
                parameters_schema=t.parameters_schema,
                is_active=t.is_active,
                created_at=t.created_at,
            )
            for t in rows
        ],
        total=total,
        offset=offset,
        limit=limit,
    )
