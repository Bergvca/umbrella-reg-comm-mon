"""Export endpoints — CSV and JSON streaming for alerts and messages."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from typing import Annotated

from elasticsearch import AsyncElasticsearch
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from umbrella_ui.auth.rbac import require_role
from umbrella_ui.db.models.alert import Alert
from umbrella_ui.deps import get_alert_session, get_es
from umbrella_ui.es.queries import build_message_search
from umbrella_ui.schemas.export import ExportFormat

router = APIRouter(prefix="/api/v1/export", tags=["export"])

_ALERT_EXPORT_CAP = 10_000
_MESSAGE_EXPORT_CAP = 10_000


# --- Alert export ---

@router.get("/alerts")
async def export_alerts(
    session: Annotated[AsyncSession, Depends(get_alert_session)],
    _user: Annotated[dict, Depends(require_role("supervisor"))],
    severity: str | None = Query(default=None),
    alert_status: str | None = Query(default=None, alias="status"),
    rule_id: str | None = Query(default=None),
    fmt: ExportFormat = Query(default=ExportFormat.csv, alias="format"),
):
    stmt = select(Alert)
    if severity:
        stmt = stmt.where(Alert.severity == severity)
    if alert_status:
        stmt = stmt.where(Alert.status == alert_status)
    if rule_id:
        stmt = stmt.where(Alert.rule_id == rule_id)
    stmt = stmt.limit(_ALERT_EXPORT_CAP)

    result = await session.execute(stmt)
    alerts = result.scalars().all()

    if fmt == ExportFormat.csv:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        filename = f"alerts-export-{timestamp}.csv"

        async def _generate():
            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow(["id", "name", "severity", "status", "rule_id", "es_index", "es_document_id", "created_at"])
            yield buf.getvalue()
            buf.seek(0)
            buf.truncate(0)
            for alert in alerts:
                writer.writerow([
                    str(alert.id), alert.name, alert.severity, alert.status,
                    str(alert.rule_id), alert.es_index, alert.es_document_id,
                    alert.created_at.isoformat(),
                ])
                yield buf.getvalue()
                buf.seek(0)
                buf.truncate(0)

        return StreamingResponse(
            _generate(),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    else:
        data = [
            {
                "id": str(a.id),
                "name": a.name,
                "severity": a.severity,
                "status": a.status,
                "rule_id": str(a.rule_id),
                "es_index": a.es_index,
                "es_document_id": a.es_document_id,
                "created_at": a.created_at.isoformat(),
            }
            for a in alerts
        ]
        return StreamingResponse(
            iter([json.dumps(data)]),
            media_type="application/json",
        )


# --- Message export ---

async def _scroll_messages(es: AsyncElasticsearch, query_body: dict, max_results: int = _MESSAGE_EXPORT_CAP):
    query_body.pop("from", None)
    query_body.pop("highlight", None)
    query_body["size"] = 1000

    resp = await es.search(index="messages-*", body=query_body, scroll="2m")
    scroll_id = resp["_scroll_id"]
    hits = resp["hits"]["hits"]
    count = 0

    try:
        while hits and count < max_results:
            for hit in hits:
                yield hit["_source"]
                count += 1
                if count >= max_results:
                    return
            resp = await es.scroll(scroll_id=scroll_id, scroll="2m")
            scroll_id = resp["_scroll_id"]
            hits = resp["hits"]["hits"]
    finally:
        await es.clear_scroll(scroll_id=scroll_id)


@router.get("/messages")
async def export_messages(
    es: Annotated[AsyncElasticsearch, Depends(get_es)],
    _user: Annotated[dict, Depends(require_role("supervisor"))],
    q: str | None = Query(default=None),
    channel: str | None = Query(default=None),
    direction: str | None = Query(default=None),
    participant: str | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    sentiment: str | None = Query(default=None),
    risk_score_min: float | None = Query(default=None),
    fmt: ExportFormat = Query(default=ExportFormat.csv, alias="format"),
):
    query_body = build_message_search(
        q=q,
        channel=channel,
        direction=direction,
        participant=participant,
        date_from=date_from,
        date_to=date_to,
        sentiment=sentiment,
        risk_score_min=risk_score_min,
    )

    if fmt == ExportFormat.csv:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        filename = f"messages-export-{timestamp}.csv"

        async def _generate():
            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow([
                "message_id", "channel", "direction", "timestamp",
                "participants", "body_text", "sentiment", "risk_score",
            ])
            yield buf.getvalue()
            buf.seek(0)
            buf.truncate(0)

            async for src in _scroll_messages(es, query_body):
                participants = "; ".join(
                    p.get("name", "") for p in src.get("participants", [])
                )
                body = (src.get("body_text") or "")[:500]
                writer.writerow([
                    src.get("message_id", ""),
                    src.get("channel", ""),
                    src.get("direction", ""),
                    src.get("timestamp", ""),
                    participants,
                    body,
                    src.get("sentiment", ""),
                    src.get("risk_score", ""),
                ])
                yield buf.getvalue()
                buf.seek(0)
                buf.truncate(0)

        return StreamingResponse(
            _generate(),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    else:
        rows = []
        async for src in _scroll_messages(es, query_body):
            rows.append(src)
        return StreamingResponse(
            iter([json.dumps(rows)]),
            media_type="application/json",
        )
