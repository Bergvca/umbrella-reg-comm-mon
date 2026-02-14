"""Risk model CRUD endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from umbrella_ui.auth.rbac import require_role
from umbrella_ui.db.models.policy import Policy, RiskModel
from umbrella_ui.deps import get_policy_session
from umbrella_ui.schemas.common import PaginatedResponse
from umbrella_ui.schemas.policy import RiskModelCreate, RiskModelDetail, RiskModelOut, RiskModelUpdate

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1/risk-models", tags=["risk-models"])


async def _risk_model_detail(rm: RiskModel, session: AsyncSession) -> RiskModelDetail:
    count_result = await session.execute(
        select(func.count()).select_from(Policy).where(Policy.risk_model_id == rm.id)
    )
    policy_count = count_result.scalar_one()
    return RiskModelDetail(
        id=rm.id,
        name=rm.name,
        description=rm.description,
        is_active=rm.is_active,
        created_by=rm.created_by,
        created_at=rm.created_at,
        updated_at=rm.updated_at,
        policy_count=policy_count,
    )


@router.get("", response_model=PaginatedResponse[RiskModelDetail])
async def list_risk_models(
    session: Annotated[AsyncSession, Depends(get_policy_session)],
    _user: Annotated[dict, Depends(require_role("reviewer"))],
    is_active: bool | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
):
    stmt = select(RiskModel)
    if is_active is not None:
        stmt = stmt.where(RiskModel.is_active == is_active)
    stmt = stmt.order_by(RiskModel.name)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    result = await session.execute(stmt.offset(offset).limit(limit))
    models = result.scalars().all()

    items = [await _risk_model_detail(rm, session) for rm in models]
    return PaginatedResponse(items=items, total=total, offset=offset, limit=limit)


@router.post("", response_model=RiskModelOut, status_code=status.HTTP_201_CREATED)
async def create_risk_model(
    body: RiskModelCreate,
    session: Annotated[AsyncSession, Depends(get_policy_session)],
    current_user: Annotated[dict, Depends(require_role("admin"))],
):
    rm = RiskModel(
        name=body.name,
        description=body.description,
        created_by=current_user["id"],
    )
    session.add(rm)
    try:
        await session.commit()
        await session.refresh(rm)
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Risk model name already exists")

    return RiskModelOut.model_validate(rm, from_attributes=True)


@router.get("/{risk_model_id}", response_model=RiskModelDetail)
async def get_risk_model(
    risk_model_id: UUID,
    session: Annotated[AsyncSession, Depends(get_policy_session)],
    _user: Annotated[dict, Depends(require_role("reviewer"))],
):
    result = await session.execute(select(RiskModel).where(RiskModel.id == risk_model_id))
    rm = result.scalar_one_or_none()
    if rm is None:
        raise HTTPException(status_code=404, detail="Risk model not found")
    return await _risk_model_detail(rm, session)


@router.patch("/{risk_model_id}", response_model=RiskModelOut)
async def update_risk_model(
    risk_model_id: UUID,
    body: RiskModelUpdate,
    session: Annotated[AsyncSession, Depends(get_policy_session)],
    _user: Annotated[dict, Depends(require_role("admin"))],
):
    result = await session.execute(select(RiskModel).where(RiskModel.id == risk_model_id))
    rm = result.scalar_one_or_none()
    if rm is None:
        raise HTTPException(status_code=404, detail="Risk model not found")

    if body.name is not None:
        rm.name = body.name
    if body.description is not None:
        rm.description = body.description
    if body.is_active is not None:
        rm.is_active = body.is_active

    try:
        await session.commit()
        await session.refresh(rm)
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Risk model name already exists")

    return RiskModelOut.model_validate(rm, from_attributes=True)
