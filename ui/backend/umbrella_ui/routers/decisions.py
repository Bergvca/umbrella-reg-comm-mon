"""Decision submission and history endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from umbrella_ui.auth.rbac import require_role
from umbrella_ui.db.models.alert import Alert
from umbrella_ui.db.models.review import AuditLog, Decision, DecisionStatus
from umbrella_ui.deps import get_alert_session, get_review_session
from umbrella_ui.schemas.review import DecisionCreate, DecisionOut, DecisionStatusOut

router = APIRouter(tags=["decisions"])


@router.post(
    "/api/v1/alerts/{alert_id}/decisions",
    response_model=DecisionOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_decision(
    alert_id: uuid.UUID,
    body: DecisionCreate,
    review_session: Annotated[AsyncSession, Depends(get_review_session)],
    alert_session: Annotated[AsyncSession, Depends(get_alert_session)],
    user: Annotated[dict, Depends(require_role("reviewer"))],
):
    """Submit a decision on an alert."""
    # Verify alert exists
    alert = (
        await alert_session.execute(select(Alert).where(Alert.id == alert_id))
    ).scalar_one_or_none()
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")

    # Verify decision status exists
    dec_status = (
        await review_session.execute(
            select(DecisionStatus).where(DecisionStatus.id == body.status_id)
        )
    ).scalar_one_or_none()
    if dec_status is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid decision status_id",
        )

    reviewer_id: uuid.UUID = user["id"]

    decision = Decision(
        alert_id=alert_id,
        reviewer_id=reviewer_id,
        status_id=body.status_id,
        comment=body.comment,
    )
    review_session.add(decision)
    await review_session.flush()  # get decision.id

    audit = AuditLog(
        decision_id=decision.id,
        actor_id=reviewer_id,
        action="created",
        new_values={
            "alert_id": str(alert_id),
            "status_id": str(body.status_id),
            "comment": body.comment,
        },
    )
    review_session.add(audit)
    await review_session.commit()
    await review_session.refresh(decision)

    # If terminal, close the alert using the alert session
    if dec_status.is_terminal:
        alert.status = "closed"
        await alert_session.commit()

    return DecisionOut(
        id=decision.id,
        alert_id=decision.alert_id,
        reviewer_id=decision.reviewer_id,
        status_id=decision.status_id,
        status_name=dec_status.name,
        comment=decision.comment,
        decided_at=decision.decided_at,
    )


@router.get(
    "/api/v1/alerts/{alert_id}/decisions",
    response_model=list[DecisionOut],
)
async def list_decisions(
    alert_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_review_session)],
    _user: Annotated[dict, Depends(require_role("reviewer"))],
):
    """List decision history for an alert."""
    stmt = (
        select(Decision, DecisionStatus.name.label("status_name"))
        .join(DecisionStatus, Decision.status_id == DecisionStatus.id)
        .where(Decision.alert_id == alert_id)
        .order_by(Decision.decided_at.desc())
    )
    rows = (await session.execute(stmt)).all()

    return [
        DecisionOut(
            id=d.id,
            alert_id=d.alert_id,
            reviewer_id=d.reviewer_id,
            status_id=d.status_id,
            status_name=status_name,
            comment=d.comment,
            decided_at=d.decided_at,
        )
        for d, status_name in rows
    ]


@router.get(
    "/api/v1/decision-statuses",
    response_model=list[DecisionStatusOut],
)
async def list_decision_statuses(
    session: Annotated[AsyncSession, Depends(get_review_session)],
    _user: Annotated[dict, Depends(require_role("reviewer"))],
):
    """List available decision statuses ordered by display_order."""
    stmt = select(DecisionStatus).order_by(DecisionStatus.display_order)
    statuses = (await session.execute(stmt)).scalars().all()
    return [
        DecisionStatusOut(
            id=s.id,
            name=s.name,
            description=s.description,
            is_terminal=s.is_terminal,
            display_order=s.display_order,
            created_at=s.created_at,
        )
        for s in statuses
    ]
