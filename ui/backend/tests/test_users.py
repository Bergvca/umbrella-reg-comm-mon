"""Tests for user CRUD endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from umbrella_ui.auth.password import hash_password
from umbrella_ui.config import Settings
from tests.conftest import make_admin_headers, make_reviewer_headers, make_session_mock, override_iam_session


def _make_user(username="alice", user_id=None, is_active=True):
    user = MagicMock()
    user.id = user_id or uuid.uuid4()
    user.username = username
    user.email = f"{username}@example.com"
    user.password_hash = hash_password("secret")
    user.is_active = is_active
    user.created_at = datetime.now(timezone.utc)
    user.updated_at = datetime.now(timezone.utc)
    return user


@pytest.mark.asyncio
async def test_list_users(app, settings: Settings):
    users = [_make_user("alice"), _make_user("bob")]
    session = make_session_mock(scalars=users, scalar_count=2)
    override_iam_session(app, session)
    headers = make_admin_headers(settings)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/users", headers=headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_create_user(app, settings: Settings):
    new_user = _make_user("charlie")
    session = make_session_mock(scalar=new_user)

    # refresh populates server-default fields on the ORM object
    async def _refresh(obj):
        obj.id = new_user.id
        obj.is_active = new_user.is_active
        obj.created_at = new_user.created_at
        obj.updated_at = new_user.updated_at

    session.refresh = _refresh
    override_iam_session(app, session)
    headers = make_admin_headers(settings)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(
            "/api/v1/users",
            json={"username": "charlie", "email": "charlie@example.com", "password": "pass"},
            headers=headers,
        )

    assert resp.status_code == 201
    data = resp.json()
    assert data["username"] == "charlie"
    assert "password_hash" not in data
    assert "password" not in data


@pytest.mark.asyncio
async def test_get_user_detail(app, settings: Settings):
    user_id = uuid.uuid4()
    user = _make_user(user_id=user_id)
    session = make_session_mock(scalar=user, scalars=["admin"])
    override_iam_session(app, session)
    headers = make_admin_headers(settings)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get(f"/api/v1/users/{user_id}", headers=headers)

    assert resp.status_code == 200
    data = resp.json()
    assert "roles" in data


@pytest.mark.asyncio
async def test_update_user(app, settings: Settings):
    user_id = uuid.uuid4()
    user = _make_user(user_id=user_id)
    session = make_session_mock(scalar=user)
    override_iam_session(app, session)
    headers = make_admin_headers(settings)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.patch(
            f"/api/v1/users/{user_id}",
            json={"is_active": False},
            headers=headers,
        )

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_add_user_to_group(app, settings: Settings):
    user_id = uuid.uuid4()
    group_id = uuid.uuid4()
    user = _make_user(user_id=user_id)
    group = MagicMock()
    group.id = group_id

    session = AsyncMock()
    call_num = [0]

    async def _execute(stmt, *args, **kwargs):
        result = MagicMock()
        call_num[0] += 1
        if call_num[0] == 1:
            result.scalar_one_or_none.return_value = user
        else:
            result.scalar_one_or_none.return_value = group
        return result

    session.execute = _execute
    session.commit = AsyncMock()
    session.add = MagicMock()
    session.rollback = AsyncMock()

    override_iam_session(app, session)
    headers = make_admin_headers(settings)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(
            f"/api/v1/users/{user_id}/groups",
            json={"group_id": str(group_id)},
            headers=headers,
        )

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_remove_user_from_group(app, settings: Settings):
    user_id = uuid.uuid4()
    group_id = uuid.uuid4()
    session = make_session_mock()
    override_iam_session(app, session)
    headers = make_admin_headers(settings)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.delete(
            f"/api/v1/users/{user_id}/groups/{group_id}",
            headers=headers,
        )

    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_non_admin_cannot_create_user(app, settings: Settings):
    session = make_session_mock()
    override_iam_session(app, session)
    headers = make_reviewer_headers(settings)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(
            "/api/v1/users",
            json={"username": "x", "email": "x@x.com", "password": "x"},
            headers=headers,
        )

    assert resp.status_code == 403
