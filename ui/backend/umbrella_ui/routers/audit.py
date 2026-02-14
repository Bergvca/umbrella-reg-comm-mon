"""Audit log endpoint."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from umbrella_ui.auth.rbac import require_role
from umbrella_ui.db.models.review import AuditLog, Decision
from umbrella_ui.deps import get_review_session
from umbrella_ui.schemas.common import PaginatedResponse
from umbrella_ui.schemas.review import AuditLogEntry

router = APIRouter(prefix="/api/v1/audit-log", tags=["audit"])


@router.get("", response_model=PaginatedResponse[AuditLogEntry])
async def list_audit_log(
    session: Annotated[AsyncSession, Depends(get_review_session)],
    _user: Annotated[dict, Depends(require_role("supervisor"))],
    actor_id: uuid.UUID | None = Query(default=None),
    alert_id: uuid.UUID | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
):
    """Paginated audit log (supervisor only)."""
    stmt = select(AuditLog)

    if actor_id:
        stmt = stmt.where(AuditLog.actor_id == actor_id)

    if alert_id:
        stmt = stmt.join(Decision, AuditLog.decision_id == Decision.id).where(
            Decision.alert_id == alert_id
        )

    if date_from:
        stmt = stmt.where(AuditLog.occurred_at >= date_from)
    if date_to:
        stmt = stmt.where(AuditLog.occurred_at <= date_to)

    from sqlalchemy import func
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(AuditLog.occurred_at.desc()).offset(offset).limit(limit)
    entries = (await session.execute(stmt)).scalars().all()

    items = [
        AuditLogEntry(
            id=e.id,
            decision_id=e.decision_id,
            actor_id=e.actor_id,
            action=e.action,
            old_values=e.old_values,
            new_values=e.new_values,
            occurred_at=e.occurred_at,
            ip_address=str(e.ip_address) if e.ip_address else None,
            user_agent=e.user_agent,
        )
        for e in entries
    ]

    return PaginatedResponse(items=items, total=total, offset=offset, limit=limit)
