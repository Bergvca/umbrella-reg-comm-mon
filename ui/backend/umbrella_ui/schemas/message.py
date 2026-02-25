"""Request/response schemas for message search endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from umbrella_ui.es.models import ESMessage, ESMessageHit


class MessageSearchParams(BaseModel):
    """Query parameters for GET /messages/search."""

    q: str | None = None
    channel: str | None = None
    direction: str | None = None
    participant: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    sentiment: str | None = None
    risk_score_min: float | None = None
    offset: int = 0
    limit: int = 20


class MessageSearchResponse(BaseModel):
    hits: list[ESMessageHit]
    total: int
    offset: int
    limit: int


class NLSearchRequest(BaseModel):
    """Request body for POST /messages/nl-search."""

    query: str
    offset: int = 0
    limit: int = 20


class NLSearchResponse(MessageSearchResponse):
    """Standard search response plus the generated ES query and explanation."""

    generated_query: dict
    explanation: str


class AudioUrlResponse(BaseModel):
    url: str
    expires_in: int
