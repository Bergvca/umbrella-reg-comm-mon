"""Tests for decision endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.conftest import (
    make_reviewer_headers,
    make_session_mock,
    override_alert_session,
    override_review_session,
)


def _make_alert(alert_id=None, status="open"):
    a = MagicMock()
    a.id = alert_id or uuid.uuid4()
    a.status = status
    return a


def _make_dec_status(status_id=None, name="Escalate", is_terminal=False):
    s = MagicMock()
    s.id = status_id or uuid.uuid4()
    s.name = name
    s.is_terminal = is_terminal
    s.description = None
    s.display_order = 0
    s.created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    return s


def _make_decision(alert_id, status_id, reviewer_id, comment=None):
    d = MagicMock()
    d.id = uuid.uuid4()
    d.alert_id = alert_id
    d.reviewer_id = reviewer_id
    d.status_id = status_id
    d.comment = comment
    d.decided_at = datetime(2024, 6, 1, tzinfo=timezone.utc)
    return d


@pytest.mark.asyncio
async def test_create_decision(app, client, settings):
    alert_id = uuid.uuid4()
    status_id = uuid.uuid4()
    user_id = uuid.uuid4()

    alert = _make_alert(alert_id=alert_id)
    dec_status = _make_dec_status(status_id=status_id, is_terminal=False)
    decision = _make_decision(alert_id, status_id, user_id)

    alert_session = AsyncMock()

    async def _alert_execute(stmt, *a, **kw):
        r = MagicMock()
        r.scalar_one_or_none.return_value = alert
        return r

    alert_session.execute = _alert_execute
    alert_session.commit = AsyncMock()

    review_session = AsyncMock()
    call_count = [0]

    async def _review_execute(stmt, *a, **kw):
        r = MagicMock()
        call_count[0] += 1
        if call_count[0] == 1:
            r.scalar_one_or_none.return_value = dec_status
        return r

    review_session.execute = _review_execute
    review_session.add = MagicMock()
    review_session.flush = AsyncMock()
    review_session.commit = AsyncMock()

    async def _refresh(obj):
        obj.id = decision.id
        obj.decided_at = decision.decided_at

    review_session.refresh = _refresh

    override_alert_session(app, alert_session)
    override_review_session(app, review_session)

    headers = make_reviewer_headers(settings, user_id=user_id)
    resp = await client.post(
        f"/api/v1/alerts/{alert_id}/decisions",
        json={"status_id": str(status_id), "comment": "looks fine"},
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["alert_id"] == str(alert_id)
    assert data["status_name"] == "Escalate"


@pytest.mark.asyncio
async def test_create_terminal_decision_closes_alert(app, client, settings):
    alert_id = uuid.uuid4()
    status_id = uuid.uuid4()
    user_id = uuid.uuid4()

    alert = _make_alert(alert_id=alert_id, status="open")
    dec_status = _make_dec_status(status_id=status_id, name="Close", is_terminal=True)
    decision = _make_decision(alert_id, status_id, user_id)

    alert_session = AsyncMock()

    async def _alert_execute(stmt, *a, **kw):
        r = MagicMock()
        r.scalar_one_or_none.return_value = alert
        return r

    alert_session.execute = _alert_execute
    alert_session.commit = AsyncMock()

    review_session = AsyncMock()
    call_count = [0]

    async def _review_execute(stmt, *a, **kw):
        r = MagicMock()
        call_count[0] += 1
        if call_count[0] == 1:
            r.scalar_one_or_none.return_value = dec_status
        return r

    review_session.execute = _review_execute
    review_session.add = MagicMock()
    review_session.flush = AsyncMock()
    review_session.commit = AsyncMock()

    async def _refresh(obj):
        obj.id = decision.id
        obj.decided_at = decision.decided_at

    review_session.refresh = _refresh

    override_alert_session(app, alert_session)
    override_review_session(app, review_session)

    headers = make_reviewer_headers(settings, user_id=user_id)
    resp = await client.post(
        f"/api/v1/alerts/{alert_id}/decisions",
        json={"status_id": str(status_id)},
        headers=headers,
    )
    assert resp.status_code == 201
    # Alert should be closed and alert_session committed
    assert alert.status == "closed"
    alert_session.commit.assert_called()


@pytest.mark.asyncio
async def test_create_decision_alert_not_found(app, client, settings):
    alert_session = AsyncMock()

    async def _execute(stmt, *a, **kw):
        r = MagicMock()
        r.scalar_one_or_none.return_value = None
        return r

    alert_session.execute = _execute
    alert_session.commit = AsyncMock()

    review_session = make_session_mock()
    override_alert_session(app, alert_session)
    override_review_session(app, review_session)

    headers = make_reviewer_headers(settings)
    resp = await client.post(
        f"/api/v1/alerts/{uuid.uuid4()}/decisions",
        json={"status_id": str(uuid.uuid4())},
        headers=headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_decisions(app, client, settings):
    alert_id = uuid.uuid4()
    d = _make_decision(alert_id, uuid.uuid4(), uuid.uuid4())

    review_session = AsyncMock()

    async def _execute(stmt, *a, **kw):
        r = MagicMock()
        r.all.return_value = [(d, "Escalate")]
        return r

    review_session.execute = _execute
    override_review_session(app, review_session)
    override_alert_session(app, make_session_mock())

    headers = make_reviewer_headers(settings)
    resp = await client.get(f"/api/v1/alerts/{alert_id}/decisions", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["status_name"] == "Escalate"


@pytest.mark.asyncio
async def test_list_decision_statuses(app, client, settings):
    s = _make_dec_status()

    review_session = AsyncMock()

    async def _execute(stmt, *a, **kw):
        r = MagicMock()
        r.scalars.return_value.all.return_value = [s]
        return r

    review_session.execute = _execute
    override_review_session(app, review_session)
    override_alert_session(app, make_session_mock())

    headers = make_reviewer_headers(settings)
    resp = await client.get("/api/v1/decision-statuses", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "Escalate"
