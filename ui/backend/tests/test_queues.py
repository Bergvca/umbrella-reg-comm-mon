"""Tests for queue management endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.conftest import (
    make_reviewer_headers,
    make_session_mock,
    make_supervisor_headers,
    override_review_session,
)


def _now():
    return datetime(2024, 1, 1, tzinfo=timezone.utc)


def _make_queue(queue_id=None, policy_id=None):
    q = MagicMock()
    q.id = queue_id or uuid.uuid4()
    q.name = "Test Queue"
    q.description = None
    q.policy_id = policy_id or uuid.uuid4()
    q.created_by = uuid.uuid4()
    q.created_at = _now()
    q.updated_at = _now()
    return q


def _make_batch(batch_id=None, queue_id=None, assigned_to=None, status="pending"):
    b = MagicMock()
    b.id = batch_id or uuid.uuid4()
    b.queue_id = queue_id or uuid.uuid4()
    b.name = "Batch 1"
    b.assigned_to = assigned_to
    b.assigned_by = None
    b.assigned_at = None
    b.status = status
    b.created_at = _now()
    b.updated_at = _now()
    return b


def _make_item(item_id=None, batch_id=None, alert_id=None):
    i = MagicMock()
    i.id = item_id or uuid.uuid4()
    i.batch_id = batch_id or uuid.uuid4()
    i.alert_id = alert_id or uuid.uuid4()
    i.position = 1
    i.created_at = _now()
    return i


@pytest.mark.asyncio
async def test_create_queue(app, client, settings):
    policy_id = uuid.uuid4()
    queue = _make_queue(policy_id=policy_id)

    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock(side_effect=lambda obj: None)

    async def _execute(stmt, *a, **kw):
        r = MagicMock()
        return r

    session.execute = _execute
    override_review_session(app, session)

    # After refresh, queue attributes should be accessible
    async def _refresh(obj):
        obj.id = queue.id
        obj.name = queue.name
        obj.description = queue.description
        obj.policy_id = queue.policy_id
        obj.created_by = queue.created_by
        obj.created_at = queue.created_at
        obj.updated_at = queue.updated_at

    session.refresh = _refresh

    headers = make_supervisor_headers(settings)
    resp = await client.post(
        "/api/v1/queues",
        json={"name": "Test Queue", "policy_id": str(policy_id)},
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Test Queue"


@pytest.mark.asyncio
async def test_list_queues(app, client, settings):
    queue = _make_queue()
    session = make_session_mock(scalars=[queue], scalar_count=1)
    override_review_session(app, session)

    headers = make_supervisor_headers(settings)
    resp = await client.get("/api/v1/queues", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1


@pytest.mark.asyncio
async def test_create_batch(app, client, settings):
    queue_id = uuid.uuid4()
    queue = _make_queue(queue_id=queue_id)
    batch = _make_batch(queue_id=queue_id)

    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()

    call_count = [0]

    async def _execute(stmt, *a, **kw):
        r = MagicMock()
        call_count[0] += 1
        if call_count[0] == 1:
            r.scalar_one_or_none.return_value = queue
        return r

    session.execute = _execute

    async def _refresh(obj):
        obj.id = batch.id
        obj.queue_id = batch.queue_id
        obj.name = batch.name
        obj.assigned_to = batch.assigned_to
        obj.assigned_by = batch.assigned_by
        obj.assigned_at = batch.assigned_at
        obj.status = batch.status
        obj.created_at = batch.created_at
        obj.updated_at = batch.updated_at

    session.refresh = _refresh
    override_review_session(app, session)

    headers = make_supervisor_headers(settings)
    resp = await client.post(
        f"/api/v1/queues/{queue_id}/batches",
        json={"name": "Batch 1"},
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["queue_id"] == str(queue_id)


@pytest.mark.asyncio
async def test_assign_batch(app, client, settings):
    queue_id = uuid.uuid4()
    batch_id = uuid.uuid4()
    assignee_id = uuid.uuid4()
    batch = _make_batch(batch_id=batch_id, queue_id=queue_id)

    session = AsyncMock()
    call_count = [0]

    async def _execute(stmt, *a, **kw):
        r = MagicMock()
        call_count[0] += 1
        if call_count[0] == 1:
            r.scalar_one_or_none.return_value = batch
        else:
            r.scalar_one.return_value = 2
        return r

    session.execute = _execute
    session.commit = AsyncMock()

    async def _refresh(obj):
        pass

    session.refresh = _refresh
    override_review_session(app, session)

    headers = make_supervisor_headers(settings)
    resp = await client.patch(
        f"/api/v1/queues/{queue_id}/batches/{batch_id}",
        json={"assigned_to": str(assignee_id)},
        headers=headers,
    )
    assert resp.status_code == 200
    assert batch.assigned_to == assignee_id


@pytest.mark.asyncio
async def test_add_item_to_batch(app, client, settings):
    queue_id = uuid.uuid4()
    batch_id = uuid.uuid4()
    alert_id = uuid.uuid4()

    batch = _make_batch(batch_id=batch_id, queue_id=queue_id)
    alert_mock = MagicMock()
    alert_mock.id = alert_id
    item = _make_item(batch_id=batch_id, alert_id=alert_id)

    session = AsyncMock()
    call_count = [0]

    async def _execute(stmt, *a, **kw):
        r = MagicMock()
        call_count[0] += 1
        if call_count[0] == 1:
            r.scalar_one_or_none.return_value = batch
        elif call_count[0] == 2:
            r.scalar_one_or_none.return_value = alert_mock
        return r

    session.execute = _execute
    session.add = MagicMock()
    session.commit = AsyncMock()

    async def _refresh(obj):
        obj.id = item.id
        obj.batch_id = item.batch_id
        obj.alert_id = item.alert_id
        obj.position = item.position
        obj.created_at = item.created_at

    session.refresh = _refresh
    override_review_session(app, session)

    headers = make_supervisor_headers(settings)
    resp = await client.post(
        f"/api/v1/queues/{queue_id}/batches/{batch_id}/items",
        json={"alert_id": str(alert_id), "position": 1},
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["alert_id"] == str(alert_id)


@pytest.mark.asyncio
async def test_list_batch_items(app, client, settings):
    queue_id = uuid.uuid4()
    batch_id = uuid.uuid4()
    batch = _make_batch(batch_id=batch_id, queue_id=queue_id)
    item = _make_item(batch_id=batch_id)

    session = AsyncMock()
    call_count = [0]

    async def _execute(stmt, *a, **kw):
        r = MagicMock()
        call_count[0] += 1
        if call_count[0] == 1:
            r.scalar_one_or_none.return_value = batch
        else:
            r.scalars.return_value.all.return_value = [item]
        return r

    session.execute = _execute
    override_review_session(app, session)

    headers = make_reviewer_headers(settings)
    resp = await client.get(
        f"/api/v1/queues/{queue_id}/batches/{batch_id}/items",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1


@pytest.mark.asyncio
async def test_my_queue(app, client, settings):
    user_id = uuid.uuid4()
    batch = _make_batch(assigned_to=user_id)

    session = AsyncMock()
    call_count = [0]

    async def _execute(stmt, *a, **kw):
        r = MagicMock()
        call_count[0] += 1
        if call_count[0] == 1:
            r.scalars.return_value.all.return_value = [batch]
        else:
            r.scalar_one.return_value = 0
        return r

    session.execute = _execute
    override_review_session(app, session)

    headers = make_reviewer_headers(settings, user_id=user_id)
    resp = await client.get("/api/v1/my-queue", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1


@pytest.mark.asyncio
async def test_reviewer_cannot_create_queue(app, client, settings):
    session = make_session_mock()
    override_review_session(app, session)

    headers = make_reviewer_headers(settings)
    resp = await client.post(
        "/api/v1/queues",
        json={"name": "Test Queue", "policy_id": str(uuid.uuid4())},
        headers=headers,
    )
    assert resp.status_code == 403
