"""Agent model management endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from umbrella_ui.auth.rbac import require_role
from umbrella_ui.db.models.agent import AgentModel
from umbrella_ui.deps import get_agent_session
from umbrella_ui.schemas.agent import ModelCreate, ModelOut, ModelUpdate
from umbrella_ui.schemas.common import PaginatedResponse

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/agent-models", tags=["agent-models"])


def _model_to_out(m: AgentModel) -> ModelOut:
    return ModelOut(
        id=m.id,
        name=m.name,
        provider=m.provider,
        model_id=m.model_id,
        base_url=m.base_url,
        max_tokens=m.max_tokens,
        is_active=m.is_active,
        created_by=m.created_by,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


@router.get("", response_model=PaginatedResponse[ModelOut])
async def list_models(
    session: Annotated[AsyncSession, Depends(get_agent_session)],
    _user: Annotated[dict, Depends(require_role("supervisor"))],
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
):
    total = (await session.execute(select(func.count()).select_from(AgentModel))).scalar_one()
    stmt = select(AgentModel).offset(offset).limit(limit).order_by(AgentModel.created_at.desc())
    rows = (await session.execute(stmt)).scalars().all()
    return PaginatedResponse(
        items=[_model_to_out(m) for m in rows],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.post("", response_model=ModelOut, status_code=status.HTTP_201_CREATED)
async def create_model(
    body: ModelCreate,
    session: Annotated[AsyncSession, Depends(get_agent_session)],
    current_user: Annotated[dict, Depends(require_role("admin"))],
):
    model = AgentModel(
        name=body.name,
        provider=body.provider,
        model_id=body.model_id,
        base_url=body.base_url,
        api_key_secret=body.api_key_secret,
        max_tokens=body.max_tokens,
        created_by=current_user["id"],
    )
    session.add(model)
    try:
        await session.commit()
        await session.refresh(model)
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Model with this name already exists",
        )
    return _model_to_out(model)


@router.put("/{model_id}", response_model=ModelOut)
async def update_model(
    model_id: uuid.UUID,
    body: ModelUpdate,
    session: Annotated[AsyncSession, Depends(get_agent_session)],
    _user: Annotated[dict, Depends(require_role("admin"))],
):
    model = (await session.execute(
        select(AgentModel).where(AgentModel.id == model_id)
    )).scalar_one_or_none()
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")

    if body.name is not None:
        model.name = body.name
    if body.provider is not None:
        model.provider = body.provider
    if body.model_id is not None:
        model.model_id = body.model_id
    if body.base_url is not None:
        model.base_url = body.base_url
    if body.api_key_secret is not None:
        model.api_key_secret = body.api_key_secret
    if body.max_tokens is not None:
        model.max_tokens = body.max_tokens
    if body.is_active is not None:
        model.is_active = body.is_active

    model.updated_at = datetime.now(tz=timezone.utc).replace(tzinfo=None)

    try:
        await session.commit()
        await session.refresh(model)
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Duplicate model name")

    return _model_to_out(model)


@router.delete("/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_model(
    model_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_agent_session)],
    _user: Annotated[dict, Depends(require_role("admin"))],
):
    """Soft-delete: set is_active=false."""
    model = (await session.execute(
        select(AgentModel).where(AgentModel.id == model_id)
    )).scalar_one_or_none()
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")
    model.is_active = False
    model.updated_at = datetime.now(tz=timezone.utc).replace(tzinfo=None)
    await session.commit()
