"""Pure unit tests for Elasticsearch query builders."""

from __future__ import annotations

from datetime import datetime, timezone

from umbrella_ui.es.queries import (
    build_alert_stats,
    build_batch_fetch_messages,
    build_message_search,
)


def test_build_message_search_basic():
    body = build_message_search(q="hello")
    must = body["query"]["bool"]["must"]
    assert any("multi_match" in clause for clause in must)
    assert body["query"]["bool"]["must"][0]["multi_match"]["query"] == "hello"


def test_build_message_search_with_channel():
    body = build_message_search(channel="email")
    filters = body["query"]["bool"]["filter"]
    assert {"term": {"channel": "email"}} in filters


def test_build_message_search_with_date_range():
    dt_from = datetime(2024, 1, 1, tzinfo=timezone.utc)
    dt_to = datetime(2024, 12, 31, tzinfo=timezone.utc)
    body = build_message_search(date_from=dt_from, date_to=dt_to)
    filters = body["query"]["bool"]["filter"]
    range_filter = next(f for f in filters if "range" in f)
    assert "gte" in range_filter["range"]["timestamp"]
    assert "lte" in range_filter["range"]["timestamp"]


def test_build_message_search_with_participant():
    body = build_message_search(participant="alice")
    filters = body["query"]["bool"]["filter"]
    nested = next(f for f in filters if "nested" in f)
    assert nested["nested"]["path"] == "participants"
    assert nested["nested"]["query"]["multi_match"]["query"] == "alice"


def test_build_message_search_empty():
    body = build_message_search()
    must = body["query"]["bool"]["must"]
    assert must == [{"match_all": {}}]


def test_build_alert_stats():
    body = build_alert_stats()
    assert body["size"] == 0
    assert "by_severity" in body["aggs"]
    assert "by_channel" in body["aggs"]
    assert "by_status" in body["aggs"]
    assert "over_time" in body["aggs"]


def test_build_batch_fetch_messages():
    refs = [
        {"es_index": "messages-2024", "es_document_id": "doc1"},
        {"es_index": "messages-2024", "es_document_id": "doc2"},
    ]
    body = build_batch_fetch_messages(refs)
    assert body["query"]["terms"]["message_id"] == ["doc1", "doc2"]
    assert body["size"] == 2
