"""Elasticsearch query builders for messages and alerts."""

from __future__ import annotations

from datetime import datetime
from typing import Optional


def build_message_search(
    *,
    q: str | None = None,
    channel: str | None = None,
    direction: str | None = None,
    participant: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    sentiment: str | None = None,
    risk_score_min: float | None = None,
    offset: int = 0,
    limit: int = 20,
) -> dict:
    """Build an ES query for ``messages-*``.

    Returns a dict ready to pass as ``body=`` to ``AsyncElasticsearch.search()``.
    """
    must: list[dict] = []
    filters: list[dict] = []

    if q:
        must.append({
            "multi_match": {
                "query": q,
                "fields": ["body_text", "transcript", "translated_text"],
                "type": "best_fields",
            }
        })

    if channel:
        filters.append({"term": {"channel": channel}})

    if direction:
        filters.append({"term": {"direction": direction}})

    if participant:
        filters.append({
            "nested": {
                "path": "participants",
                "query": {
                    "multi_match": {
                        "query": participant,
                        "fields": ["participants.name", "participants.id"],
                    }
                },
            }
        })

    if date_from or date_to:
        range_q: dict = {}
        if date_from:
            range_q["gte"] = date_from.isoformat()
        if date_to:
            range_q["lte"] = date_to.isoformat()
        filters.append({"range": {"timestamp": range_q}})

    if sentiment:
        filters.append({"term": {"sentiment": sentiment}})

    if risk_score_min is not None:
        filters.append({"range": {"risk_score": {"gte": risk_score_min}}})

    body: dict = {
        "query": {
            "bool": {
                "must": must or [{"match_all": {}}],
                "filter": filters,
            }
        },
        "highlight": {
            "fields": {
                "body_text": {},
                "transcript": {},
                "translated_text": {},
            }
        },
        "sort": [{"timestamp": {"order": "desc"}}],
        "from": offset,
        "size": limit,
    }

    return body


def build_alert_stats(
    *,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    policy_id: str | None = None,
    severity: str | None = None,
) -> dict:
    """Build an ES aggregation query for ``alerts-*`` dashboard stats.

    Optional filters narrow the documents before aggregation.
    When no filters are provided, all documents are included (match_all behavior).
    """
    filters: list[dict] = []

    if date_from or date_to:
        range_q: dict = {}
        if date_from:
            range_q["gte"] = date_from.isoformat()
        if date_to:
            range_q["lte"] = date_to.isoformat()
        filters.append({"range": {"timestamp": range_q}})

    if policy_id:
        filters.append({"term": {"policy_id": policy_id}})

    if severity:
        filters.append({"term": {"severity": severity}})

    body: dict = {
        "size": 0,
        "aggs": {
            "by_severity": {"terms": {"field": "severity"}},
            "by_channel": {"terms": {"field": "channel"}},
            "by_status": {"terms": {"field": "review_status"}},
            "over_time": {
                "date_histogram": {
                    "field": "timestamp",
                    "calendar_interval": "day",
                }
            },
        },
    }

    if filters:
        body["query"] = {"bool": {"filter": filters}}

    return body


def build_batch_fetch_messages(es_refs: list[dict]) -> dict:
    """Build a multi-get-style bool query to fetch messages by (index, doc_id) pairs.

    ``es_refs`` is a list of ``{"es_index": "...", "es_document_id": "..."}``.

    Uses a ``terms`` query on ``message_id`` across all relevant indices.
    Returns a query body suitable for ``es.search()``.
    """
    doc_ids = [ref["es_document_id"] for ref in es_refs]
    return {
        "query": {
            "terms": {"message_id": doc_ids}
        },
        "size": len(doc_ids),
    }
