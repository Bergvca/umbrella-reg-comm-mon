"""Trade search and retrieval endpoints backed by Elasticsearch."""

from __future__ import annotations

from typing import Annotated

import structlog
from elasticsearch import AsyncElasticsearch, NotFoundError
from fastapi import APIRouter, Depends, HTTPException, Query, status

from umbrella_ui.auth.rbac import require_role
from umbrella_ui.deps import get_es
from umbrella_ui.es.models import ESTrade, ESTradeHit, ESTradeMetadata
from umbrella_ui.es.queries import build_trade_search, build_trade_stats
from umbrella_ui.schemas.trade import TradeAggBucket, TradeSearchResponse, TradeStatsResponse

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/trades", tags=["trades"])


@router.get("/search", response_model=TradeSearchResponse)
async def search_trades(
    es: Annotated[AsyncElasticsearch, Depends(get_es)],
    _user: Annotated[dict, Depends(require_role("reviewer"))],
    q: str | None = Query(default=None),
    ticker: str | None = Query(default=None),
    side: str | None = Query(default=None),
    participant: str | None = Query(default=None),
    venue: str | None = Query(default=None),
    account_id: str | None = Query(default=None),
    quantity_min: float | None = Query(default=None),
    quantity_max: float | None = Query(default=None),
    price_min: float | None = Query(default=None),
    price_max: float | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
):
    """Full-text and filtered search over ``trades-*``."""
    from datetime import datetime

    def _parse_dt(s: str | None):
        if s is None:
            return None
        return datetime.fromisoformat(s)

    body = build_trade_search(
        q=q,
        ticker=ticker,
        side=side,
        participant=participant,
        venue=venue,
        account_id=account_id,
        quantity_min=quantity_min,
        quantity_max=quantity_max,
        price_min=price_min,
        price_max=price_max,
        date_from=_parse_dt(date_from),
        date_to=_parse_dt(date_to),
        offset=offset,
        limit=limit,
    )

    resp = await es.search(index="trades-*", body=body)
    hits_data = resp.get("hits", {})
    total = hits_data.get("total", {}).get("value", 0)

    hits: list[ESTradeHit] = []
    for hit in hits_data.get("hits", []):
        try:
            source = hit["_source"]
            metadata_raw = source.get("metadata", {})
            metadata = ESTradeMetadata.model_validate(metadata_raw)
            trade = ESTrade(
                message_id=source["message_id"],
                channel=source.get("channel", "trade_data"),
                direction=source.get("direction"),
                timestamp=source["timestamp"],
                participants=[],
                body_text=source.get("body_text"),
                metadata=metadata,
            )
            # Parse nested participants
            for p in source.get("participants", []):
                from umbrella_ui.es.models import ESParticipant
                trade.participants.append(ESParticipant.model_validate(p))

            hits.append(ESTradeHit(
                trade=trade,
                index=hit["_index"],
                score=hit.get("_score"),
            ))
        except Exception:
            logger.warning("trade_hit_parse_failed", doc_id=hit.get("_id"), exc_info=True)

    return TradeSearchResponse(hits=hits, total=total, offset=offset, limit=limit)


@router.get("/stats", response_model=TradeStatsResponse)
async def trade_stats(
    es: Annotated[AsyncElasticsearch, Depends(get_es)],
    _user: Annotated[dict, Depends(require_role("reviewer"))],
    participant: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
):
    """Aggregated trade statistics over ``trades-*``."""
    from datetime import datetime

    def _parse_dt(s: str | None):
        if s is None:
            return None
        return datetime.fromisoformat(s)

    body = build_trade_stats(
        date_from=_parse_dt(date_from),
        date_to=_parse_dt(date_to),
        participant=participant,
    )

    resp = await es.search(index="trades-*", body=body)
    aggs = resp.get("aggregations", {})

    by_ticker = []
    for bucket in aggs.get("by_ticker", {}).get("buckets", []):
        by_ticker.append(TradeAggBucket(
            key=bucket["key"],
            doc_count=bucket["doc_count"],
            total_quantity=bucket.get("total_quantity", {}).get("value"),
            total_notional=bucket.get("total_notional", {}).get("value"),
        ))

    by_side = [
        TradeAggBucket(key=b["key"], doc_count=b["doc_count"])
        for b in aggs.get("by_side", {}).get("buckets", [])
    ]
    by_venue = [
        TradeAggBucket(key=b["key"], doc_count=b["doc_count"])
        for b in aggs.get("by_venue", {}).get("buckets", [])
    ]

    total_trades = resp.get("hits", {}).get("total", {}).get("value", 0)

    return TradeStatsResponse(
        by_ticker=by_ticker,
        by_side=by_side,
        by_venue=by_venue,
        total_trades=total_trades,
    )


@router.get("/{index}/{doc_id}", response_model=ESTrade)
async def get_trade(
    index: str,
    doc_id: str,
    es: Annotated[AsyncElasticsearch, Depends(get_es)],
    _user: Annotated[dict, Depends(require_role("reviewer"))],
):
    """Fetch a single trade document from Elasticsearch."""
    try:
        doc = await es.get(index=index, id=doc_id)
    except NotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trade not found")
    except Exception:
        logger.warning("get_trade_es_error", index=index, doc_id=doc_id, exc_info=True)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trade not found")

    source = doc["_source"]
    metadata_raw = source.get("metadata", {})
    metadata = ESTradeMetadata.model_validate(metadata_raw)
    trade = ESTrade(
        message_id=source["message_id"],
        channel=source.get("channel", "trade_data"),
        direction=source.get("direction"),
        timestamp=source["timestamp"],
        participants=[],
        body_text=source.get("body_text"),
        metadata=metadata,
    )
    for p in source.get("participants", []):
        from umbrella_ui.es.models import ESParticipant
        trade.participants.append(ESParticipant.model_validate(p))

    return trade
