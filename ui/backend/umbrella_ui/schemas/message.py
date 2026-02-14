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


class AudioUrlResponse(BaseModel):
    url: str
    expires_in: int
