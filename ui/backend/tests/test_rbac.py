"""Tests for RBAC role hierarchy and enforcement."""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from umbrella_ui.auth.jwt import create_access_token
from umbrella_ui.config import Settings
from tests.conftest import make_session_mock, override_iam_session


def _headers(settings: Settings, roles: list[str]) -> dict:
    token = create_access_token(uuid.uuid4(), roles, settings)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_admin_can_access_admin_endpoint(app, settings: Settings):
    session = make_session_mock(scalars=[], scalar_count=0)
    override_iam_session(app, session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/users", headers=_headers(settings, ["admin"]))

    assert resp.status_code != 403


@pytest.mark.asyncio
async def test_reviewer_cannot_access_admin_endpoint(app, settings: Settings):
    session = make_session_mock()
    override_iam_session(app, session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/users", headers=_headers(settings, ["reviewer"]))

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_supervisor_can_access_reviewer_endpoint(app, settings: Settings):
    session = make_session_mock(scalars=[])
    override_iam_session(app, session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/roles", headers=_headers(settings, ["supervisor"]))

    assert resp.status_code != 403


@pytest.mark.asyncio
async def test_admin_can_access_reviewer_endpoint(app, settings: Settings):
    session = make_session_mock(scalars=[])
    override_iam_session(app, session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/roles", headers=_headers(settings, ["admin"]))

    assert resp.status_code != 403


@pytest.mark.asyncio
async def test_no_roles_gets_403(app, settings: Settings):
    session = make_session_mock()
    override_iam_session(app, session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/users", headers=_headers(settings, []))

    assert resp.status_code == 403
