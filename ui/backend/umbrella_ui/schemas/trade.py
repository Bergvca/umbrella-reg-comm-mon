"""Request/response schemas for trade search endpoints."""

from __future__ import annotations

from pydantic import BaseModel

from umbrella_ui.es.models import ESTradeHit


class TradeSearchResponse(BaseModel):
    hits: list[ESTradeHit]
    total: int
    offset: int
    limit: int


class TradeAggBucket(BaseModel):
    key: str
    doc_count: int
    total_quantity: float | None = None
    total_notional: float | None = None


class TradeStatsResponse(BaseModel):
    by_ticker: list[TradeAggBucket] = []
    by_side: list[TradeAggBucket] = []
    by_venue: list[TradeAggBucket] = []
    total_trades: int = 0
