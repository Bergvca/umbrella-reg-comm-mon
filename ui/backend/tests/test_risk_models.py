"""Tests for risk model CRUD endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.conftest import (
    make_admin_headers,
    make_reviewer_headers,
    make_session_mock,
    override_policy_session,
)
from umbrella_ui.db.models.policy import RiskModel


def _make_risk_model(**kwargs) -> RiskModel:
    defaults = {
        "id": uuid.uuid4(),
        "name": "Test Model",
        "description": None,
        "is_active": True,
        "created_by": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    defaults.update(kwargs)
    rm = MagicMock(spec=RiskModel)
    for k, v in defaults.items():
        setattr(rm, k, v)
    return rm


@pytest.mark.asyncio
async def test_list_risk_models(app, client, settings):
    rm = _make_risk_model()
    session = AsyncMock()
    call_count = 0

    async def _execute(stmt, *args, **kwargs):
        nonlocal call_count
        result = MagicMock()
        call_count += 1
        if call_count == 1:
            # total count
            result.scalar_one.return_value = 1
        elif call_count == 2:
            # list query
            result.scalars.return_value.all.return_value = [rm]
        else:
            # policy_count per model
            result.scalar_one.return_value = 2
        return result

    session.execute = _execute
    override_policy_session(app, session)

    resp = await client.get("/api/v1/risk-models", headers=make_reviewer_headers(settings))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["policy_count"] == 2


@pytest.mark.asyncio
async def test_list_risk_models_filter_active(app, client, settings):
    session = AsyncMock()
    call_count = 0

    async def _execute(stmt, *args, **kwargs):
        nonlocal call_count
        result = MagicMock()
        call_count += 1
        if call_count == 1:
            result.scalar_one.return_value = 0
        elif call_count == 2:
            result.scalars.return_value.all.return_value = []
        else:
            result.scalar_one.return_value = 0
        return result

    session.execute = _execute
    override_policy_session(app, session)

    resp = await client.get("/api/v1/risk-models?is_active=true", headers=make_reviewer_headers(settings))
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


@pytest.mark.asyncio
async def test_create_risk_model(app, client, settings):
    rm = _make_risk_model(name="New Model")
    session = AsyncMock()

    added_objects = []
    def _add(obj):
        added_objects.append(obj)

    async def _refresh(obj):
        # Populate server-default fields on the newly-created ORM object
        obj.id = rm.id
        obj.is_active = rm.is_active
        obj.created_at = rm.created_at
        obj.updated_at = rm.updated_at
        obj.created_by = rm.created_by

    session.add = _add
    session.commit = AsyncMock()
    session.refresh = _refresh
    override_policy_session(app, session)

    resp = await client.post(
        "/api/v1/risk-models",
        json={"name": "New Model"},
        headers=make_admin_headers(settings),
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "New Model"


@pytest.mark.asyncio
async def test_create_risk_model_duplicate(app, client, settings):
    from sqlalchemy.exc import IntegrityError

    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock(side_effect=IntegrityError("", {}, None))
    session.rollback = AsyncMock()
    override_policy_session(app, session)

    resp = await client.post(
        "/api/v1/risk-models",
        json={"name": "Duplicate"},
        headers=make_admin_headers(settings),
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_create_risk_model_reviewer_forbidden(app, client, settings):
    override_policy_session(app, AsyncMock())
    resp = await client.post(
        "/api/v1/risk-models",
        json={"name": "X"},
        headers=make_reviewer_headers(settings),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_risk_model(app, client, settings):
    rm = _make_risk_model()
    session = AsyncMock()
    call_count = 0

    async def _execute(stmt, *args, **kwargs):
        nonlocal call_count
        result = MagicMock()
        call_count += 1
        if call_count == 1:
            result.scalar_one_or_none.return_value = rm
        else:
            result.scalar_one.return_value = 3
        return result

    session.execute = _execute
    override_policy_session(app, session)

    resp = await client.get(f"/api/v1/risk-models/{rm.id}", headers=make_reviewer_headers(settings))
    assert resp.status_code == 200
    assert resp.json()["id"] == str(rm.id)


@pytest.mark.asyncio
async def test_get_risk_model_not_found(app, client, settings):
    session = AsyncMock()

    async def _execute(stmt, *args, **kwargs):
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        return result

    session.execute = _execute
    override_policy_session(app, session)

    resp = await client.get(f"/api/v1/risk-models/{uuid.uuid4()}", headers=make_reviewer_headers(settings))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_risk_model(app, client, settings):
    rm = _make_risk_model(name="Old Name")
    session = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    async def _execute(stmt, *args, **kwargs):
        result = MagicMock()
        result.scalar_one_or_none.return_value = rm
        return result

    session.execute = _execute
    override_policy_session(app, session)

    resp = await client.patch(
        f"/api/v1/risk-models/{rm.id}",
        json={"name": "New Name"},
        headers=make_admin_headers(settings),
    )
    assert resp.status_code == 200
    assert rm.name == "New Name"


@pytest.mark.asyncio
async def test_update_risk_model_deactivate(app, client, settings):
    rm = _make_risk_model(is_active=True)
    session = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    async def _execute(stmt, *args, **kwargs):
        result = MagicMock()
        result.scalar_one_or_none.return_value = rm
        return result

    session.execute = _execute
    override_policy_session(app, session)

    resp = await client.patch(
        f"/api/v1/risk-models/{rm.id}",
        json={"is_active": False},
        headers=make_admin_headers(settings),
    )
    assert resp.status_code == 200
    assert rm.is_active is False
