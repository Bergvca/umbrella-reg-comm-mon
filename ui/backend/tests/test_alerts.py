"""Tests for alert endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.conftest import (
    make_reviewer_headers,
    make_session_mock,
    make_supervisor_headers,
    override_alert_session,
    override_es,
)


def _make_alert(
    alert_id=None,
    severity="high",
    status="open",
    rule_id=None,
    es_index="messages-2024",
    es_document_id="doc1",
):
    alert = MagicMock()
    alert.id = alert_id or uuid.uuid4()
    alert.name = "Test Alert"
    alert.rule_id = rule_id or uuid.uuid4()
    alert.es_index = es_index
    alert.es_document_id = es_document_id
    alert.es_document_ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
    alert.severity = severity
    alert.status = status
    alert.created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    return alert


def _make_es_response(doc_id="doc1", message_id="doc1"):
    return {
        "hits": {
            "total": {"value": 1},
            "hits": [
                {
                    "_index": "messages-2024",
                    "_id": doc_id,
                    "_score": 1.0,
                    "_source": {
                        "message_id": message_id,
                        "channel": "email",
                        "timestamp": "2024-01-01T00:00:00Z",
                    },
                }
            ],
        }
    }


@pytest.mark.asyncio
async def test_list_alerts(app, client, settings):
    alert = _make_alert()
    session = make_session_mock(scalars=[alert], scalar_count=1)
    override_alert_session(app, session)

    es_mock = AsyncMock()
    es_mock.search = AsyncMock(return_value=_make_es_response(alert.es_document_id, alert.es_document_id))
    override_es(app, es_mock)

    headers = make_reviewer_headers(settings)
    resp = await client.get("/api/v1/alerts", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert data["total"] == 1


@pytest.mark.asyncio
async def test_list_alerts_filter_by_severity(app, client, settings):
    alert = _make_alert(severity="high")
    session = make_session_mock(scalars=[alert], scalar_count=1)
    override_alert_session(app, session)

    es_mock = AsyncMock()
    es_mock.search = AsyncMock(return_value={"hits": {"total": {"value": 0}, "hits": []}})
    override_es(app, es_mock)

    headers = make_reviewer_headers(settings)
    resp = await client.get("/api/v1/alerts?severity=high", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_alert_detail(app, client, settings):
    alert_id = uuid.uuid4()
    alert = _make_alert(alert_id=alert_id)

    session = AsyncMock()
    row = MagicMock()
    row.__iter__ = MagicMock(return_value=iter([alert, "Test Rule", "Test Policy"]))

    async def _execute(stmt, *args, **kwargs):
        result = MagicMock()
        result.first.return_value = (alert, "Test Rule", "Test Policy")
        return result

    session.execute = _execute

    override_alert_session(app, session)

    es_mock = AsyncMock()
    es_mock.get = AsyncMock(return_value={
        "_source": {
            "message_id": "doc1",
            "channel": "email",
            "timestamp": "2024-01-01T00:00:00Z",
        }
    })
    override_es(app, es_mock)

    headers = make_reviewer_headers(settings)
    resp = await client.get(f"/api/v1/alerts/{alert_id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(alert_id)
    assert data["rule_name"] == "Test Rule"
    assert data["policy_name"] == "Test Policy"


@pytest.mark.asyncio
async def test_get_alert_not_found(app, client, settings):
    session = AsyncMock()

    async def _execute(stmt, *args, **kwargs):
        result = MagicMock()
        result.first.return_value = None
        return result

    session.execute = _execute
    override_alert_session(app, session)

    es_mock = AsyncMock()
    override_es(app, es_mock)

    headers = make_reviewer_headers(settings)
    resp = await client.get(f"/api/v1/alerts/{uuid.uuid4()}", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_alert_status(app, client, settings):
    alert_id = uuid.uuid4()
    alert = _make_alert(alert_id=alert_id, status="open")

    session = AsyncMock()

    async def _execute(stmt, *args, **kwargs):
        result = MagicMock()
        result.scalar_one_or_none.return_value = alert
        result.scalar_one.return_value = 1
        return result

    session.execute = _execute
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    override_alert_session(app, session)

    es_mock = AsyncMock()
    override_es(app, es_mock)

    headers = make_reviewer_headers(settings)
    resp = await client.patch(
        f"/api/v1/alerts/{alert_id}/status",
        json={"status": "in_review"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert alert.status == "in_review"


@pytest.mark.asyncio
async def test_update_alert_invalid_status(app, client, settings):
    alert_id = uuid.uuid4()
    session = make_session_mock()
    override_alert_session(app, session)
    es_mock = AsyncMock()
    override_es(app, es_mock)

    headers = make_reviewer_headers(settings)
    resp = await client.patch(
        f"/api/v1/alerts/{alert_id}/status",
        json={"status": "invalid_status"},
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_alert_stats(app, client, settings):
    session = make_session_mock()
    override_alert_session(app, session)

    es_mock = AsyncMock()
    es_mock.search = AsyncMock(return_value={
        "aggregations": {
            "by_severity": {"buckets": [{"key": "high", "doc_count": 5}]},
            "by_channel": {"buckets": [{"key": "email", "doc_count": 3}]},
            "by_status": {"buckets": [{"key": "open", "doc_count": 4}]},
            "over_time": {"buckets": [{"key_as_string": "2024-01-01", "doc_count": 2}]},
        }
    })
    override_es(app, es_mock)

    headers = make_supervisor_headers(settings)
    resp = await client.get("/api/v1/alerts/stats", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["by_severity"][0]["key"] == "high"


@pytest.mark.asyncio
async def test_reviewer_can_list_alerts(app, client, settings):
    alert = _make_alert()
    session = make_session_mock(scalars=[alert], scalar_count=1)
    override_alert_session(app, session)

    es_mock = AsyncMock()
    es_mock.search = AsyncMock(return_value={"hits": {"total": {"value": 0}, "hits": []}})
    override_es(app, es_mock)

    headers = make_reviewer_headers(settings)
    resp = await client.get("/api/v1/alerts", headers=headers)
    assert resp.status_code == 200
