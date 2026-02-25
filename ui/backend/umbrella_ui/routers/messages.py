"""Message search and retrieval endpoints backed by Elasticsearch."""

from __future__ import annotations

from typing import Annotated

import boto3
import httpx
import structlog
from elasticsearch import AsyncElasticsearch, NotFoundError
from fastapi import APIRouter, Depends, HTTPException, Query, status

from umbrella_ui.auth.rbac import require_role
from umbrella_ui.config import Settings
from umbrella_ui.deps import get_es, get_settings
from umbrella_ui.es.models import ESMessage, ESMessageHit
from umbrella_ui.es.queries import build_message_search
from umbrella_ui.schemas.message import AudioUrlResponse, MessageSearchResponse, NLSearchRequest, NLSearchResponse

logger = structlog.get_logger()

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


def _validate_es_query(query: dict) -> None:
    """Reject dangerous ES query constructs (scripts, write ops).

    Checks recursively by key name to avoid false positives from field names
    that happen to contain forbidden substrings (e.g. "transcript" ⊃ "script").
    """
    FORBIDDEN_KEYS = {"script", "script_score", "script_fields", "_update", "_delete", "_bulk"}

    def _walk(node: object) -> None:
        if isinstance(node, dict):
            for key, val in node.items():
                if key in FORBIDDEN_KEYS:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=f"Generated query contains forbidden construct: {key}",
                    )
                _walk(val)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(query)


DEFAULT_FIELD_SCHEMA: dict[str, str] = {
    "body_text": "text",
    "transcript": "text",
    "translated_text": "text",
    "channel": "keyword",
    "direction": "keyword",
    "timestamp": "date",
    "participants.name": "text",
    "participants.id": "keyword",
    "sentiment": "keyword",
    "risk_score": "float",
}


@router.post("/nl-search", response_model=NLSearchResponse)
async def nl_search(
    body: NLSearchRequest,
    es: Annotated[AsyncElasticsearch, Depends(get_es)],
    settings: Annotated[Settings, Depends(get_settings)],
    _user: Annotated[dict, Depends(require_role("reviewer"))],
):
    """Natural language search over ``messages-*``.

    Proxies the query to the agent runtime for NL→ES translation,
    validates the result, then executes against Elasticsearch.
    """
    # 1. Call agent runtime to translate NL → ES query DSL
    translate_url = f"{settings.agents_base_url}/translate-query"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                translate_url,
                json={
                    "natural_language_query": body.query,
                    "index_pattern": "messages-*",
                    "field_schema": DEFAULT_FIELD_SCHEMA,
                },
            )
            resp.raise_for_status()
            translation = resp.json()
    except httpx.HTTPStatusError as exc:
        logger.error("translate_query_failed", status=exc.response.status_code)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Agent runtime query translation failed",
        )
    except httpx.RequestError as exc:
        logger.error("translate_query_unreachable", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Agent runtime unreachable",
        )

    es_query = translation["es_query"]
    explanation = translation.get("explanation", "")

    # 2. Validate the generated query
    _validate_es_query(es_query)

    # 3. Inject pagination
    es_query["from"] = body.offset
    es_query["size"] = body.limit

    # 4. Execute against messages-*
    es_resp = await es.search(index="messages-*", body=es_query)
    hits_data = es_resp.get("hits", {})
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

    return NLSearchResponse(
        hits=hits,
        total=total,
        offset=body.offset,
        limit=body.limit,
        generated_query=es_query,
        explanation=explanation,
    )


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
