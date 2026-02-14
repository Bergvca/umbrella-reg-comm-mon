"""Policy, rule, and group-policy assignment endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from umbrella_ui.auth.rbac import require_role
from umbrella_ui.db.models.iam import Group
from umbrella_ui.db.models.policy import GroupPolicy, Policy, RiskModel, Rule
from umbrella_ui.deps import get_policy_session
from umbrella_ui.schemas.common import PaginatedResponse
from umbrella_ui.schemas.policy import (
    AssignGroupPolicy,
    GroupPolicyOut,
    PolicyCreate,
    PolicyDetail,
    PolicyOut,
    PolicyUpdate,
    RuleCreate,
    RuleOut,
    RuleUpdate,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1/policies", tags=["policies"])
rules_router = APIRouter(prefix="/api/v1/rules", tags=["rules"])


async def _policy_detail(policy: Policy, session: AsyncSession) -> PolicyDetail:
    rm_result = await session.execute(
        select(RiskModel.name).where(RiskModel.id == policy.risk_model_id)
    )
    risk_model_name = rm_result.scalar_one()

    rule_count_result = await session.execute(
        select(func.count()).select_from(Rule).where(Rule.policy_id == policy.id)
    )
    rule_count = rule_count_result.scalar_one()

    group_count_result = await session.execute(
        select(func.count()).select_from(GroupPolicy).where(GroupPolicy.policy_id == policy.id)
    )
    group_count = group_count_result.scalar_one()

    return PolicyDetail(
        id=policy.id,
        risk_model_id=policy.risk_model_id,
        name=policy.name,
        description=policy.description,
        is_active=policy.is_active,
        created_by=policy.created_by,
        created_at=policy.created_at,
        updated_at=policy.updated_at,
        risk_model_name=risk_model_name,
        rule_count=rule_count,
        group_count=group_count,
    )


# --- Policy endpoints ---

@router.get("", response_model=PaginatedResponse[PolicyDetail])
async def list_policies(
    session: Annotated[AsyncSession, Depends(get_policy_session)],
    _user: Annotated[dict, Depends(require_role("reviewer"))],
    risk_model_id: UUID | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
):
    stmt = select(Policy)
    if risk_model_id is not None:
        stmt = stmt.where(Policy.risk_model_id == risk_model_id)
    if is_active is not None:
        stmt = stmt.where(Policy.is_active == is_active)
    stmt = stmt.order_by(Policy.name)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    result = await session.execute(stmt.offset(offset).limit(limit))
    policies = result.scalars().all()

    items = [await _policy_detail(p, session) for p in policies]
    return PaginatedResponse(items=items, total=total, offset=offset, limit=limit)


@router.post("", response_model=PolicyOut, status_code=status.HTTP_201_CREATED)
async def create_policy(
    body: PolicyCreate,
    session: Annotated[AsyncSession, Depends(get_policy_session)],
    current_user: Annotated[dict, Depends(require_role("admin"))],
):
    rm_result = await session.execute(
        select(RiskModel).where(RiskModel.id == body.risk_model_id)
    )
    if rm_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Risk model not found")

    policy = Policy(
        risk_model_id=body.risk_model_id,
        name=body.name,
        description=body.description,
        created_by=current_user["id"],
    )
    session.add(policy)
    try:
        await session.commit()
        await session.refresh(policy)
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Policy name already exists for this risk model")

    return PolicyOut.model_validate(policy, from_attributes=True)


@router.get("/{policy_id}", response_model=PolicyDetail)
async def get_policy(
    policy_id: UUID,
    session: Annotated[AsyncSession, Depends(get_policy_session)],
    _user: Annotated[dict, Depends(require_role("reviewer"))],
):
    result = await session.execute(select(Policy).where(Policy.id == policy_id))
    policy = result.scalar_one_or_none()
    if policy is None:
        raise HTTPException(status_code=404, detail="Policy not found")
    return await _policy_detail(policy, session)


@router.patch("/{policy_id}", response_model=PolicyOut)
async def update_policy(
    policy_id: UUID,
    body: PolicyUpdate,
    session: Annotated[AsyncSession, Depends(get_policy_session)],
    _user: Annotated[dict, Depends(require_role("admin"))],
):
    result = await session.execute(select(Policy).where(Policy.id == policy_id))
    policy = result.scalar_one_or_none()
    if policy is None:
        raise HTTPException(status_code=404, detail="Policy not found")

    if body.name is not None:
        policy.name = body.name
    if body.description is not None:
        policy.description = body.description
    if body.is_active is not None:
        policy.is_active = body.is_active

    await session.commit()
    await session.refresh(policy)
    return PolicyOut.model_validate(policy, from_attributes=True)


# --- Rule endpoints (nested under policies) ---

@router.get("/{policy_id}/rules", response_model=PaginatedResponse[RuleOut])
async def list_rules(
    policy_id: UUID,
    session: Annotated[AsyncSession, Depends(get_policy_session)],
    _user: Annotated[dict, Depends(require_role("reviewer"))],
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
):
    policy_result = await session.execute(select(Policy).where(Policy.id == policy_id))
    if policy_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Policy not found")

    stmt = select(Rule).where(Rule.policy_id == policy_id).order_by(Rule.name)
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    result = await session.execute(stmt.offset(offset).limit(limit))
    rules = result.scalars().all()

    items = [RuleOut.model_validate(r, from_attributes=True) for r in rules]
    return PaginatedResponse(items=items, total=total, offset=offset, limit=limit)


@router.post("/{policy_id}/rules", response_model=RuleOut, status_code=status.HTTP_201_CREATED)
async def create_rule(
    policy_id: UUID,
    body: RuleCreate,
    session: Annotated[AsyncSession, Depends(get_policy_session)],
    current_user: Annotated[dict, Depends(require_role("admin"))],
):
    policy_result = await session.execute(select(Policy).where(Policy.id == policy_id))
    if policy_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Policy not found")

    rule = Rule(
        policy_id=policy_id,
        name=body.name,
        description=body.description,
        kql=body.kql,
        severity=body.severity,
        created_by=current_user["id"],
    )
    session.add(rule)
    await session.commit()
    await session.refresh(rule)
    return RuleOut.model_validate(rule, from_attributes=True)


# --- Rule endpoints (top-level /rules/{id}) ---

@rules_router.get("/{rule_id}", response_model=RuleOut)
async def get_rule(
    rule_id: UUID,
    session: Annotated[AsyncSession, Depends(get_policy_session)],
    _user: Annotated[dict, Depends(require_role("reviewer"))],
):
    result = await session.execute(select(Rule).where(Rule.id == rule_id))
    rule = result.scalar_one_or_none()
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    return RuleOut.model_validate(rule, from_attributes=True)


@rules_router.patch("/{rule_id}", response_model=RuleOut)
async def update_rule(
    rule_id: UUID,
    body: RuleUpdate,
    session: Annotated[AsyncSession, Depends(get_policy_session)],
    _user: Annotated[dict, Depends(require_role("admin"))],
):
    result = await session.execute(select(Rule).where(Rule.id == rule_id))
    rule = result.scalar_one_or_none()
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")

    if body.name is not None:
        rule.name = body.name
    if body.description is not None:
        rule.description = body.description
    if body.kql is not None:
        rule.kql = body.kql
    if body.severity is not None:
        rule.severity = body.severity
    if body.is_active is not None:
        rule.is_active = body.is_active

    await session.commit()
    await session.refresh(rule)
    return RuleOut.model_validate(rule, from_attributes=True)


@rules_router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(
    rule_id: UUID,
    session: Annotated[AsyncSession, Depends(get_policy_session)],
    _user: Annotated[dict, Depends(require_role("admin"))],
):
    result = await session.execute(select(Rule).where(Rule.id == rule_id))
    rule = result.scalar_one_or_none()
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")

    rule.is_active = False
    await session.commit()


# --- Group-policy assignment endpoints ---

@router.get("/{policy_id}/groups", response_model=list[GroupPolicyOut])
async def list_group_policies(
    policy_id: UUID,
    session: Annotated[AsyncSession, Depends(get_policy_session)],
    _user: Annotated[dict, Depends(require_role("admin"))],
):
    result = await session.execute(select(Policy).where(Policy.id == policy_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Policy not found")

    gp_result = await session.execute(
        select(GroupPolicy).where(GroupPolicy.policy_id == policy_id)
    )
    gps = gp_result.scalars().all()
    return [GroupPolicyOut.model_validate(gp, from_attributes=True) for gp in gps]


@router.post("/{policy_id}/groups", status_code=status.HTTP_200_OK)
async def assign_group_policy(
    policy_id: UUID,
    body: AssignGroupPolicy,
    session: Annotated[AsyncSession, Depends(get_policy_session)],
    current_user: Annotated[dict, Depends(require_role("admin"))],
):
    policy_result = await session.execute(select(Policy).where(Policy.id == policy_id))
    if policy_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Policy not found")

    group_result = await session.execute(select(Group).where(Group.id == body.group_id))
    if group_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Group not found")

    gp = GroupPolicy(
        group_id=body.group_id,
        policy_id=policy_id,
        assigned_by=current_user["id"],
    )
    session.add(gp)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Group already assigned to this policy")

    return {"ok": True}


@router.delete("/{policy_id}/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_group_policy(
    policy_id: UUID,
    group_id: UUID,
    session: Annotated[AsyncSession, Depends(get_policy_session)],
    _user: Annotated[dict, Depends(require_role("admin"))],
):
    await session.execute(
        delete(GroupPolicy).where(
            GroupPolicy.policy_id == policy_id,
            GroupPolicy.group_id == group_id,
        )
    )
    await session.commit()
