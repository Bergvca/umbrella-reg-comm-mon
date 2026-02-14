"""Tests for export endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.conftest import (
    make_admin_headers,
    make_reviewer_headers,
    make_supervisor_headers,
    override_alert_session,
    override_es,
)
from umbrella_ui.db.models.alert import Alert


def _make_alert(**kwargs) -> Alert:
    defaults = {
        "id": uuid.uuid4(),
        "name": "Test Alert",
        "rule_id": uuid.uuid4(),
        "es_index": "messages-2024",
        "es_document_id": "doc-1",
        "es_document_ts": None,
        "severity": "high",
        "status": "open",
        "created_at": datetime.now(timezone.utc),
    }
    defaults.update(kwargs)
    a = MagicMock(spec=Alert)
    for k, v in defaults.items():
        setattr(a, k, v)
    return a


@pytest.mark.asyncio
async def test_export_alerts_csv(app, client, settings):
    alert = _make_alert()
    session = AsyncMock()

    async def _execute(stmt, *args, **kwargs):
        result = MagicMock()
        result.scalars.return_value.all.return_value = [alert]
        return result

    session.execute = _execute
    override_alert_session(app, session)

    resp = await client.get("/api/v1/export/alerts", headers=make_supervisor_headers(settings))
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    lines = resp.text.strip().split("\n")
    assert lines[0].startswith("id,name,severity")
    assert len(lines) == 2  # header + 1 data row


@pytest.mark.asyncio
async def test_export_alerts_json(app, client, settings):
    alert = _make_alert()
    session = AsyncMock()

    async def _execute(stmt, *args, **kwargs):
        result = MagicMock()
        result.scalars.return_value.all.return_value = [alert]
        return result

    session.execute = _execute
    override_alert_session(app, session)

    resp = await client.get(
        "/api/v1/export/alerts?format=json",
        headers=make_supervisor_headers(settings),
    )
    assert resp.status_code == 200
    assert "application/json" in resp.headers["content-type"]
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["severity"] == "high"


@pytest.mark.asyncio
async def test_export_alerts_with_filters(app, client, settings):
    session = AsyncMock()

    async def _execute(stmt, *args, **kwargs):
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        return result

    session.execute = _execute
    override_alert_session(app, session)

    resp = await client.get(
        "/api/v1/export/alerts?severity=low&status=open",
        headers=make_supervisor_headers(settings),
    )
    assert resp.status_code == 200
    lines = resp.text.strip().split("\n")
    assert len(lines) == 1  # header only


@pytest.mark.asyncio
async def test_export_alerts_supervisor_only(app, client, settings):
    override_alert_session(app, AsyncMock())

    resp = await client.get("/api/v1/export/alerts", headers=make_reviewer_headers(settings))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_export_messages_csv(app, client, settings):
    es_mock = AsyncMock()
    es_mock.search = AsyncMock(return_value={
        "_scroll_id": "scroll-1",
        "hits": {
            "hits": [
                {
                    "_source": {
                        "message_id": "msg-1",
                        "channel": "email",
                        "direction": "inbound",
                        "timestamp": "2024-01-01T00:00:00Z",
                        "participants": [{"name": "Alice"}, {"name": "Bob"}],
                        "body_text": "Hello world",
                        "sentiment": "neutral",
                        "risk_score": 0.1,
                    }
                }
            ]
        },
    })
    es_mock.scroll = AsyncMock(return_value={
        "_scroll_id": "scroll-1",
        "hits": {"hits": []},
    })
    es_mock.clear_scroll = AsyncMock()
    override_es(app, es_mock)

    resp = await client.get("/api/v1/export/messages", headers=make_supervisor_headers(settings))
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    lines = resp.text.strip().split("\n")
    assert lines[0].startswith("message_id,channel")
    assert len(lines) == 2


@pytest.mark.asyncio
async def test_export_messages_json(app, client, settings):
    es_mock = AsyncMock()
    es_mock.search = AsyncMock(return_value={
        "_scroll_id": "scroll-1",
        "hits": {
            "hits": [
                {"_source": {"message_id": "msg-1", "channel": "teams"}}
            ]
        },
    })
    es_mock.scroll = AsyncMock(return_value={
        "_scroll_id": "scroll-1",
        "hits": {"hits": []},
    })
    es_mock.clear_scroll = AsyncMock()
    override_es(app, es_mock)

    resp = await client.get(
        "/api/v1/export/messages?format=json",
        headers=make_supervisor_headers(settings),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert data[0]["channel"] == "teams"


@pytest.mark.asyncio
async def test_export_messages_empty(app, client, settings):
    es_mock = AsyncMock()
    es_mock.search = AsyncMock(return_value={
        "_scroll_id": "scroll-1",
        "hits": {"hits": []},
    })
    es_mock.scroll = AsyncMock(return_value={
        "_scroll_id": "scroll-1",
        "hits": {"hits": []},
    })
    es_mock.clear_scroll = AsyncMock()
    override_es(app, es_mock)

    resp = await client.get("/api/v1/export/messages", headers=make_supervisor_headers(settings))
    assert resp.status_code == 200
    lines = resp.text.strip().split("\n")
    assert len(lines) == 1  # header only
