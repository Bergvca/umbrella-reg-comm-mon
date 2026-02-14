"""Alert endpoints — hybrid PG + Elasticsearch query pattern."""

from __future__ import annotations

import uuid
from typing import Annotated

from elasticsearch import AsyncElasticsearch, NotFoundError
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from umbrella_ui.auth.rbac import require_role
from umbrella_ui.db.models.alert import Alert
from umbrella_ui.db.models.policy import Policy, Rule
from umbrella_ui.deps import get_alert_session, get_es
from umbrella_ui.es.models import AlertStats, AlertStatsBucket, AlertTimePoint, ESMessage
from umbrella_ui.es.queries import build_alert_stats, build_batch_fetch_messages
from umbrella_ui.schemas.alert import AlertOut, AlertStatusUpdate, AlertWithMessage
from umbrella_ui.schemas.common import PaginatedResponse

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])

_VALID_STATUSES = {"open", "in_review", "closed"}


@router.get("/stats", response_model=AlertStats)
async def get_alert_stats(
    es: Annotated[AsyncElasticsearch, Depends(get_es)],
    _user: Annotated[dict, Depends(require_role("supervisor"))],
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    severity: str | None = Query(default=None),
):
    """ES aggregations for dashboard stats."""
    from datetime import datetime as _dt

    _date_from = _dt.fromisoformat(date_from) if date_from else None
    _date_to = _dt.fromisoformat(date_to) if date_to else None

    resp = await es.search(
        index="alerts-*",
        body=build_alert_stats(date_from=_date_from, date_to=_date_to, severity=severity),
    )
    aggs = resp.get("aggregations", {})

    def _buckets(key: str) -> list[AlertStatsBucket]:
        return [
            AlertStatsBucket(key=str(b["key"]), doc_count=b["doc_count"])
            for b in aggs.get(key, {}).get("buckets", [])
        ]

    over_time = [
        AlertTimePoint(
            key_as_string=b["key_as_string"],
            doc_count=b["doc_count"],
        )
        for b in aggs.get("over_time", {}).get("buckets", [])
    ]

    return AlertStats(
        by_severity=_buckets("by_severity"),
        by_channel=_buckets("by_channel"),
        by_status=_buckets("by_status"),
        over_time=over_time,
    )


@router.get("", response_model=PaginatedResponse[AlertOut])
async def list_alerts(
    session: Annotated[AsyncSession, Depends(get_alert_session)],
    es: Annotated[AsyncElasticsearch, Depends(get_es)],
    _user: Annotated[dict, Depends(require_role("reviewer"))],
    severity: str | None = Query(default=None),
    alert_status: str | None = Query(default=None, alias="status"),
    rule_id: uuid.UUID | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
):
    """List alerts with optional filters. Batch-fetches ES message previews."""
    stmt = select(Alert)
    if severity:
        stmt = stmt.where(Alert.severity == severity)
    if alert_status:
        stmt = stmt.where(Alert.status == alert_status)
    if rule_id:
        stmt = stmt.where(Alert.rule_id == rule_id)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    stmt = stmt.offset(offset).limit(limit)
    alerts = (await session.execute(stmt)).scalars().all()

    # Batch-fetch linked ES messages
    es_lookup: dict[str, ESMessage] = {}
    if alerts:
        refs = [{"es_index": a.es_index, "es_document_id": a.es_document_id} for a in alerts]
        try:
            es_resp = await es.search(index="messages-*", body=build_batch_fetch_messages(refs))
            for hit in es_resp.get("hits", {}).get("hits", []):
                try:
                    msg = ESMessage.model_validate(hit["_source"])
                    es_lookup[hit["_source"].get("message_id", hit["_id"])] = msg
                except Exception:
                    pass
        except Exception:
            pass

    items = [
        AlertOut(
            id=a.id,
            name=a.name,
            rule_id=a.rule_id,
            es_index=a.es_index,
            es_document_id=a.es_document_id,
            es_document_ts=a.es_document_ts,
            severity=a.severity,
            status=a.status,
            created_at=a.created_at,
        )
        for a in alerts
    ]

    return PaginatedResponse(items=items, total=total, offset=offset, limit=limit)


@router.get("/{alert_id}", response_model=AlertWithMessage)
async def get_alert(
    alert_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_alert_session)],
    es: Annotated[AsyncElasticsearch, Depends(get_es)],
    _user: Annotated[dict, Depends(require_role("reviewer"))],
):
    """Alert detail with full linked ES message, rule name, and policy name."""
    stmt = (
        select(Alert, Rule.name.label("rule_name"), Policy.name.label("policy_name"))
        .join(Rule, Alert.rule_id == Rule.id)
        .join(Policy, Rule.policy_id == Policy.id)
        .where(Alert.id == alert_id)
    )
    row = (await session.execute(stmt)).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")

    alert, rule_name, policy_name = row

    message: ESMessage | None = None
    try:
        es_doc = await es.get(index=alert.es_index, id=alert.es_document_id)
        message = ESMessage.model_validate(es_doc["_source"])
    except NotFoundError:
        pass

    return AlertWithMessage(
        id=alert.id,
        name=alert.name,
        rule_id=alert.rule_id,
        es_index=alert.es_index,
        es_document_id=alert.es_document_id,
        es_document_ts=alert.es_document_ts,
        severity=alert.severity,
        status=alert.status,
        created_at=alert.created_at,
        rule_name=rule_name,
        policy_name=policy_name,
        message=message,
    )


@router.patch("/{alert_id}/status", response_model=AlertOut)
async def update_alert_status(
    alert_id: uuid.UUID,
    body: AlertStatusUpdate,
    session: Annotated[AsyncSession, Depends(get_alert_session)],
    _user: Annotated[dict, Depends(require_role("reviewer"))],
):
    """Update the status of an alert."""
    if body.status not in _VALID_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid status. Must be one of: {sorted(_VALID_STATUSES)}",
        )

    alert = (
        await session.execute(select(Alert).where(Alert.id == alert_id))
    ).scalar_one_or_none()
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")

    alert.status = body.status
    await session.commit()
    await session.refresh(alert)

    return AlertOut(
        id=alert.id,
        name=alert.name,
        rule_id=alert.rule_id,
        es_index=alert.es_index,
        es_document_id=alert.es_document_id,
        es_document_ts=alert.es_document_ts,
        severity=alert.severity,
        status=alert.status,
        created_at=alert.created_at,
    )
