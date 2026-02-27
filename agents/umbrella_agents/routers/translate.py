"""Natural language → Elasticsearch query translation endpoint."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from umbrella_agents.executor import _ensure_model_registered
from umbrella_agents.model_router import translate_nl_to_es_query

logger = structlog.get_logger()

router = APIRouter(tags=["translate"])


class TranslateRequest(BaseModel):
    natural_language_query: str
    index_pattern: str = "messages-*"
    field_schema: dict[str, str] = {
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


class TranslateResponse(BaseModel):
    es_query: dict
    explanation: str


@router.post("/translate-query", response_model=TranslateResponse)
async def translate_query(body: TranslateRequest, request: Request):
    """Translate a natural language query into Elasticsearch query DSL."""
    settings = request.app.state.settings

    # Load default model from DB, or fall back to config
    # For now, we attempt to load the first active model from the DB
    model_str = "openai/gpt-4o"
    api_key = None
    base_url = None

    try:
        async with request.app.state.db.session_factory() as session:
            from sqlalchemy import select
            from umbrella_agents.db.models import Model

            stmt = select(Model).where(Model.is_active.is_(True)).limit(1)
            result = await session.execute(stmt)
            model_row = result.scalar_one_or_none()
            if model_row:
                model_str = _ensure_model_registered(model_row)
                base_url = model_row.base_url
    except Exception:
        logger.warning("model_db_lookup_failed", exc_info=True)

    try:
        result = await translate_nl_to_es_query(
            query=body.natural_language_query,
            field_schema=body.field_schema,
            model=model_str,
            api_key=api_key,
            base_url=base_url,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Translation failed: {exc}",
        )
    except Exception as exc:
        logger.error("translate_query_error", error=str(exc), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="LLM service unavailable",
        )

    return TranslateResponse(
        es_query=result["es_query"],
        explanation=result["explanation"],
    )
