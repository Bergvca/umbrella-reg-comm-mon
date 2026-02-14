"""Message search and retrieval endpoints backed by Elasticsearch."""

from __future__ import annotations

from typing import Annotated

import boto3
from elasticsearch import AsyncElasticsearch, NotFoundError
from fastapi import APIRouter, Depends, HTTPException, Query, status

from umbrella_ui.auth.rbac import require_role
from umbrella_ui.config import Settings
from umbrella_ui.deps import get_es, get_settings
from umbrella_ui.es.models import ESMessage, ESMessageHit
from umbrella_ui.es.queries import build_message_search
from umbrella_ui.schemas.message import AudioUrlResponse, MessageSearchResponse

router = APIRouter(prefix="/api/v1/messages", tags=["messages"])


def generate_presigned_url(s3_uri: str, settings: Settings) -> str:
    """Parse ``s3://bucket/key`` and return a pre-signed GET URL."""
    path = s3_uri.removeprefix("s3://")
    bucket, _, key = path.partition("/")
    s3_client = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        region_name=settings.s3_region,
    )
    return s3_client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=settings.s3_presigned_url_expiry,
    )


@router.get("/search", response_model=MessageSearchResponse)
async def search_messages(
    es: Annotated[AsyncElasticsearch, Depends(get_es)],
    _user: Annotated[dict, Depends(require_role("reviewer"))],
    q: str | None = Query(default=None),
    channel: str | None = Query(default=None),
    direction: str | None = Query(default=None),
    participant: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    sentiment: str | None = Query(default=None),
    risk_score_min: float | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
):
    """Full-text search over ``messages-*``."""
    from datetime import datetime

    def _parse_dt(s: str | None):
        if s is None:
            return None
        return datetime.fromisoformat(s)

    body = build_message_search(
        q=q,
        channel=channel,
        direction=direction,
        participant=participant,
        date_from=_parse_dt(date_from),
        date_to=_parse_dt(date_to),
        sentiment=sentiment,
        risk_score_min=risk_score_min,
        offset=offset,
        limit=limit,
    )

    resp = await es.search(index="messages-*", body=body)
    hits_data = resp.get("hits", {})
    total = hits_data.get("total", {}).get("value", 0)

    hits: list[ESMessageHit] = []
    for hit in hits_data.get("hits", []):
        try:
            msg = ESMessage.model_validate(hit["_source"])
            highlights = {
                field: frags
                for field, frags in (hit.get("highlight") or {}).items()
            }
            hits.append(ESMessageHit(
                message=msg,
                index=hit["_index"],
                score=hit.get("_score"),
                highlights=highlights,
            ))
        except Exception:
            pass

    return MessageSearchResponse(hits=hits, total=total, offset=offset, limit=limit)


@router.get("/{index}/{doc_id}", response_model=ESMessage)
async def get_message(
    index: str,
    doc_id: str,
    es: Annotated[AsyncElasticsearch, Depends(get_es)],
    _user: Annotated[dict, Depends(require_role("reviewer"))],
):
    """Fetch a single message from Elasticsearch."""
    try:
        doc = await es.get(index=index, id=doc_id)
    except NotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    return ESMessage.model_validate(doc["_source"])


@router.get("/{index}/{doc_id}/audio", response_model=AudioUrlResponse)
async def get_audio_url(
    index: str,
    doc_id: str,
    es: Annotated[AsyncElasticsearch, Depends(get_es)],
    settings: Annotated[Settings, Depends(get_settings)],
    _user: Annotated[dict, Depends(require_role("reviewer"))],
):
    """Generate a pre-signed S3 URL for audio playback."""
    try:
        doc = await es.get(index=index, id=doc_id)
    except NotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    msg = ESMessage.model_validate(doc["_source"])
    if msg.audio_ref is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No audio for this message")

    url = generate_presigned_url(msg.audio_ref, settings)
    return AudioUrlResponse(url=url, expires_in=settings.s3_presigned_url_expiry)
