"""Tests for authentication endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from umbrella_ui.auth.jwt import create_access_token, create_refresh_token
from umbrella_ui.auth.password import hash_password
from umbrella_ui.config import Settings
from tests.conftest import make_admin_headers, make_session_mock, override_iam_session


def _make_user(username="alice", password="secret", is_active=True, user_id=None):
    user = MagicMock()
    user.id = user_id or uuid.uuid4()
    user.username = username
    user.email = f"{username}@example.com"
    user.password_hash = hash_password(password)
    user.is_active = is_active
    user.created_at = datetime.now(timezone.utc)
    user.updated_at = datetime.now(timezone.utc)
    return user


@pytest.mark.asyncio
async def test_login_success(app, settings: Settings):
    user = _make_user()
    session = make_session_mock(scalar=user, scalars=["admin"])
    override_iam_session(app, session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(
            "/api/v1/auth/login",
            json={"username": "alice", "password": "secret"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(app, settings: Settings):
    user = _make_user(password="correct")
    session = make_session_mock(scalar=user)
    override_iam_session(app, session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(
            "/api/v1/auth/login",
            json={"username": "alice", "password": "wrong"},
        )

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_unknown_user(app):
    session = make_session_mock(scalar=None)
    override_iam_session(app, session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(
            "/api/v1/auth/login",
            json={"username": "nobody", "password": "x"},
        )

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_inactive_user(app):
    user = _make_user(is_active=False)
    session = make_session_mock(scalar=user)
    override_iam_session(app, session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(
            "/api/v1/auth/login",
            json={"username": "alice", "password": "secret"},
        )

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_me_valid_token(app, settings: Settings):
    user_id = uuid.uuid4()
    user = _make_user(user_id=user_id)
    session = make_session_mock(scalar=user, scalars=["admin"])
    override_iam_session(app, session)
    headers = make_admin_headers(settings, user_id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/auth/me", headers=headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "alice"


@pytest.mark.asyncio
async def test_me_no_token(client: AsyncClient):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code in (401, 403)  # no token → unauthenticated


@pytest.mark.asyncio
async def test_me_expired_token(client: AsyncClient, settings: Settings):
    from jose import jwt as jose_jwt

    payload = {
        "sub": str(uuid.uuid4()),
        "roles": ["admin"],
        "exp": 1,  # epoch 1 = expired
        "type": "access",
    }
    expired_token = jose_jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

    resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_success(app, settings: Settings):
    user_id = uuid.uuid4()
    user = _make_user(user_id=user_id)
    session = make_session_mock(scalar=user, scalars=["admin"])
    override_iam_session(app, session)
    refresh_token = create_refresh_token(user_id, settings)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data


@pytest.mark.asyncio
async def test_refresh_with_access_token(app, settings: Settings):
    user_id = uuid.uuid4()
    access_token = create_access_token(user_id, ["admin"], settings)
    session = make_session_mock()
    override_iam_session(app, session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": access_token},
        )
    assert resp.status_code == 401
