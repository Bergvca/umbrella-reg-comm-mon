"""Shared test fixtures for the UI backend."""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from umbrella_ui.app import create_app
from umbrella_ui.auth.jwt import create_access_token
from umbrella_ui.auth.password import hash_password
from umbrella_ui.config import Settings
from umbrella_ui.deps import get_alert_session, get_es, get_iam_session, get_policy_session, get_review_session, get_settings


def _test_settings(**overrides) -> Settings:
    """Create Settings with test defaults."""
    defaults = {
        "iam_database_url": "sqlite+aiosqlite://",
        "policy_database_url": "sqlite+aiosqlite://",
        "alert_database_url": "sqlite+aiosqlite://",
        "review_database_url": "sqlite+aiosqlite://",
        "jwt_secret": "test-secret",
    }
    defaults.update(overrides)
    return Settings(**defaults)


@pytest.fixture
def settings():
    return _test_settings()


@pytest.fixture
async def app(settings):
    application = create_app(settings)
    return application


@pytest.fixture
async def client(app):
    """Async HTTP test client. Lifespan is not started — use dependency_overrides."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


def make_session_mock(scalar=None, scalars=None, scalar_count=0):
    """Build an async session mock."""
    session = AsyncMock()

    async def _execute(stmt, *args, **kwargs):
        result = MagicMock()
        result.scalar_one_or_none.return_value = scalar
        result.scalar_one.return_value = scalar_count
        result.scalars.return_value.all.return_value = scalars or []
        return result

    session.execute = _execute
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    session.rollback = AsyncMock()
    return session


def override_iam_session(app, session):
    """Override the iam session dependency on the app."""

    async def _get_session():
        yield session

    app.dependency_overrides[get_iam_session] = _get_session
    return app


def make_admin_headers(settings: Settings, user_id: uuid.UUID | None = None) -> dict:
    uid = user_id or uuid.uuid4()
    token = create_access_token(uid, ["admin"], settings)
    return {"Authorization": f"Bearer {token}"}


def make_reviewer_headers(settings: Settings, user_id: uuid.UUID | None = None) -> dict:
    uid = user_id or uuid.uuid4()
    token = create_access_token(uid, ["reviewer"], settings)
    return {"Authorization": f"Bearer {token}"}


def override_alert_session(app, session):
    async def _get_session():
        yield session
    app.dependency_overrides[get_alert_session] = _get_session


def override_review_session(app, session):
    async def _get_session():
        yield session
    app.dependency_overrides[get_review_session] = _get_session


def override_es(app, es_mock):
    def _get_es():
        return es_mock
    app.dependency_overrides[get_es] = _get_es


def override_policy_session(app, session):
    async def _get_session():
        yield session
    app.dependency_overrides[get_policy_session] = _get_session


def make_supervisor_headers(settings: Settings, user_id: uuid.UUID | None = None) -> dict:
    uid = user_id or uuid.uuid4()
    token = create_access_token(uid, ["supervisor"], settings)
    return {"Authorization": f"Bearer {token}"}
