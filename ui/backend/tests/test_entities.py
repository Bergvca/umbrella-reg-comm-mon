"""Tests for entity CRUD endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from umbrella_ui.config import Settings
from tests.conftest import make_admin_headers, make_reviewer_headers, make_session_mock, override_entity_session


def _make_entity(display_name="Jane Smith", entity_type="person", entity_id=None):
    entity = MagicMock()
    entity.id = entity_id or uuid.uuid4()
    entity.display_name = display_name
    entity.entity_type = entity_type
    entity.created_at = datetime.now(timezone.utc)
    entity.updated_at = datetime.now(timezone.utc)
    entity.created_by = uuid.uuid4()
    entity.handles = []
    entity.attributes = []
    return entity


def _make_handle(entity_id=None, handle_type="email", handle_value="jane@acme.com"):
    handle = MagicMock()
    handle.id = uuid.uuid4()
    handle.entity_id = entity_id or uuid.uuid4()
    handle.handle_type = handle_type
    handle.handle_value = handle_value
    handle.is_primary = True
    handle.created_at = datetime.now(timezone.utc)
    return handle


@pytest.mark.asyncio
async def test_list_entities(app, settings: Settings):
    entities = [_make_entity("Jane Smith"), _make_entity("Acme Corp", "organization")]
    session = make_session_mock(scalars=entities, scalar_count=2)
    override_entity_session(app, session)
    headers = make_admin_headers(settings)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/entities", headers=headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_create_entity(app, settings: Settings):
    entity = _make_entity("Jane Smith")
    session = make_session_mock(scalar=entity)

    async def _refresh(obj, **kwargs):
        obj.id = entity.id
        obj.display_name = entity.display_name
        obj.entity_type = entity.entity_type
        obj.created_at = entity.created_at
        obj.updated_at = entity.updated_at
        obj.created_by = entity.created_by
        obj.handles = []
        obj.attributes = []

    session.refresh = _refresh
    override_entity_session(app, session)
    headers = make_admin_headers(settings)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(
            "/api/v1/entities",
            json={
                "display_name": "Jane Smith",
                "entity_type": "person",
                "handles": [{"handle_type": "email", "handle_value": "jane@acme.com", "is_primary": True}],
            },
            headers=headers,
        )

    assert resp.status_code == 201
    data = resp.json()
    assert data["display_name"] == "Jane Smith"


@pytest.mark.asyncio
async def test_get_entity(app, settings: Settings):
    entity_id = uuid.uuid4()
    entity = _make_entity(entity_id=entity_id)
    handle = _make_handle(entity_id=entity_id)
    entity.handles = [handle]
    session = make_session_mock(scalar=entity)
    override_entity_session(app, session)
    headers = make_admin_headers(settings)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get(f"/api/v1/entities/{entity_id}", headers=headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["display_name"] == "Jane Smith"
    assert len(data["handles"]) == 1


@pytest.mark.asyncio
async def test_delete_entity(app, settings: Settings):
    entity_id = uuid.uuid4()
    entity = _make_entity(entity_id=entity_id)
    session = make_session_mock(scalar=entity)
    session.delete = AsyncMock()
    override_entity_session(app, session)
    headers = make_admin_headers(settings)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.delete(f"/api/v1/entities/{entity_id}", headers=headers)

    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_entity_not_found(app, settings: Settings):
    session = make_session_mock(scalar=None)
    override_entity_session(app, session)
    headers = make_admin_headers(settings)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.delete(f"/api/v1/entities/{uuid.uuid4()}", headers=headers)

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_reviewer_cannot_create_entity(app, settings: Settings):
    session = make_session_mock()
    override_entity_session(app, session)
    headers = make_reviewer_headers(settings)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(
            "/api/v1/entities",
            json={"display_name": "X", "entity_type": "person"},
            headers=headers,
        )

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_reviewer_can_list_entities(app, settings: Settings):
    session = make_session_mock(scalars=[], scalar_count=0)
    override_entity_session(app, session)
    headers = make_reviewer_headers(settings)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/entities", headers=headers)

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_add_handle(app, settings: Settings):
    entity_id = uuid.uuid4()
    entity = _make_entity(entity_id=entity_id)
    handle = _make_handle(entity_id=entity_id)

    session = AsyncMock()
    call_num = [0]

    async def _execute(stmt, *args, **kwargs):
        result = MagicMock()
        call_num[0] += 1
        result.scalar_one_or_none.return_value = entity
        return result

    session.execute = _execute
    session.commit = AsyncMock()
    session.add = MagicMock()
    session.rollback = AsyncMock()

    async def _refresh(obj, **kwargs):
        obj.id = handle.id
        obj.entity_id = entity_id
        obj.handle_type = handle.handle_type
        obj.handle_value = handle.handle_value
        obj.is_primary = handle.is_primary
        obj.created_at = handle.created_at

    session.refresh = _refresh
    override_entity_session(app, session)
    headers = make_admin_headers(settings)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(
            f"/api/v1/entities/{entity_id}/handles",
            json={"handle_type": "email", "handle_value": "jane@acme.com", "is_primary": True},
            headers=headers,
        )

    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_batch_upload_json(app, settings: Settings):
    session = AsyncMock()

    async def _execute(stmt, *args, **kwargs):
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        return result

    session.execute = _execute
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()
    session.rollback = AsyncMock()
    override_entity_session(app, session)
    headers = make_admin_headers(settings)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(
            "/api/v1/entities/batch",
            json=[
                {
                    "display_name": "Jane Smith",
                    "entity_type": "person",
                    "handles": [{"handle_type": "email", "handle_value": "jane@acme.com"}],
                },
                {
                    "display_name": "Acme Corp",
                    "entity_type": "organization",
                    "handles": [],
                },
            ],
            headers=headers,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["created"] == 2
    assert data["errors"] == []
