"""Tests for group CRUD endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from umbrella_ui.config import Settings
from tests.conftest import make_admin_headers, make_session_mock, override_iam_session


def _make_group(name="admins", group_id=None):
    group = MagicMock()
    group.id = group_id or uuid.uuid4()
    group.name = name
    group.description = None
    group.created_at = datetime.now(timezone.utc)
    group.updated_at = datetime.now(timezone.utc)
    return group


def _make_user(username="alice", user_id=None):
    user = MagicMock()
    user.id = user_id or uuid.uuid4()
    user.username = username
    user.email = f"{username}@example.com"
    user.is_active = True
    user.created_at = datetime.now(timezone.utc)
    user.updated_at = datetime.now(timezone.utc)
    return user


@pytest.mark.asyncio
async def test_create_group(app, settings: Settings):
    group = _make_group("reviewers")
    session = make_session_mock(scalar=group)

    async def _refresh(obj):
        obj.id = group.id
        obj.created_at = group.created_at
        obj.updated_at = group.updated_at

    session.refresh = _refresh
    override_iam_session(app, session)
    headers = make_admin_headers(settings)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(
            "/api/v1/groups",
            json={"name": "reviewers"},
            headers=headers,
        )

    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "reviewers"


@pytest.mark.asyncio
async def test_list_groups(app, settings: Settings):
    groups = [_make_group("admins"), _make_group("reviewers")]

    # The list_groups handler queries: count(*), then groups, then per-group roles+count
    session = AsyncMock()
    call_num = [0]

    async def _execute(stmt, *args, **kwargs):
        result = MagicMock()
        call_num[0] += 1
        if call_num[0] == 1:
            # total count
            result.scalar_one.return_value = 2
        elif call_num[0] == 2:
            # group list
            result.scalars.return_value.all.return_value = groups
        else:
            # per-group role names and member counts (alternating)
            result.scalars.return_value.all.return_value = []
            result.scalar_one.return_value = 0
        return result

    session.execute = _execute
    session.commit = AsyncMock()
    session.add = MagicMock()

    override_iam_session(app, session)
    headers = make_admin_headers(settings)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/groups", headers=headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2


@pytest.mark.asyncio
async def test_assign_role_to_group(app, settings: Settings):
    group_id = uuid.uuid4()
    role_id = uuid.uuid4()
    group = _make_group(group_id=group_id)
    role = MagicMock()
    role.id = role_id

    session = AsyncMock()
    call_num = [0]

    async def _execute(stmt, *args, **kwargs):
        result = MagicMock()
        call_num[0] += 1
        if call_num[0] == 1:
            result.scalar_one_or_none.return_value = group
        else:
            result.scalar_one_or_none.return_value = role
        return result

    session.execute = _execute
    session.commit = AsyncMock()
    session.add = MagicMock()
    session.rollback = AsyncMock()

    override_iam_session(app, session)
    headers = make_admin_headers(settings)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(
            f"/api/v1/groups/{group_id}/roles",
            json={"role_id": str(role_id)},
            headers=headers,
        )

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_remove_role_from_group(app, settings: Settings):
    group_id = uuid.uuid4()
    role_id = uuid.uuid4()
    session = make_session_mock()
    override_iam_session(app, session)
    headers = make_admin_headers(settings)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.delete(
            f"/api/v1/groups/{group_id}/roles/{role_id}",
            headers=headers,
        )

    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_list_group_members(app, settings: Settings):
    group_id = uuid.uuid4()
    group = _make_group(group_id=group_id)
    users = [_make_user("alice"), _make_user("bob")]
    session = make_session_mock(scalar=group, scalars=users)
    override_iam_session(app, session)
    headers = make_admin_headers(settings)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get(
            f"/api/v1/groups/{group_id}/members",
            headers=headers,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
