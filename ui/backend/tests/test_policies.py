"""Tests for policy, rule, and group-policy assignment endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.conftest import (
    make_admin_headers,
    make_reviewer_headers,
    override_policy_session,
)
from umbrella_ui.db.models.policy import GroupPolicy, Policy, RiskModel, Rule


def _now():
    return datetime.now(timezone.utc)


def _make_policy(**kwargs) -> Policy:
    defaults = {
        "id": uuid.uuid4(),
        "risk_model_id": uuid.uuid4(),
        "name": "Test Policy",
        "description": None,
        "is_active": True,
        "created_by": None,
        "created_at": _now(),
        "updated_at": _now(),
    }
    defaults.update(kwargs)
    p = MagicMock(spec=Policy)
    for k, v in defaults.items():
        setattr(p, k, v)
    return p


def _make_rule(**kwargs) -> Rule:
    defaults = {
        "id": uuid.uuid4(),
        "policy_id": uuid.uuid4(),
        "name": "Test Rule",
        "description": None,
        "kql": "severity:high",
        "severity": "high",
        "is_active": True,
        "created_by": None,
        "created_at": _now(),
        "updated_at": _now(),
    }
    defaults.update(kwargs)
    r = MagicMock(spec=Rule)
    for k, v in defaults.items():
        setattr(r, k, v)
    return r


def _make_group_policy(**kwargs) -> GroupPolicy:
    defaults = {
        "group_id": uuid.uuid4(),
        "policy_id": uuid.uuid4(),
        "assigned_by": None,
        "assigned_at": _now(),
    }
    defaults.update(kwargs)
    gp = MagicMock(spec=GroupPolicy)
    for k, v in defaults.items():
        setattr(gp, k, v)
    return gp


# --- Policy tests ---

@pytest.mark.asyncio
async def test_list_policies(app, client, settings):
    policy = _make_policy()
    session = AsyncMock()
    call_count = 0

    async def _execute(stmt, *args, **kwargs):
        nonlocal call_count
        result = MagicMock()
        call_count += 1
        if call_count == 1:
            result.scalar_one.return_value = 1
        elif call_count == 2:
            result.scalars.return_value.all.return_value = [policy]
        elif call_count == 3:
            # risk_model_name
            result.scalar_one.return_value = "Risk Model A"
        elif call_count == 4:
            # rule_count
            result.scalar_one.return_value = 5
        else:
            # group_count
            result.scalar_one.return_value = 2
        return result

    session.execute = _execute
    override_policy_session(app, session)

    resp = await client.get("/api/v1/policies", headers=make_reviewer_headers(settings))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["rule_count"] == 5
    assert data["items"][0]["group_count"] == 2


@pytest.mark.asyncio
async def test_list_policies_filter_by_risk_model(app, client, settings):
    session = AsyncMock()
    call_count = 0

    async def _execute(stmt, *args, **kwargs):
        nonlocal call_count
        result = MagicMock()
        call_count += 1
        if call_count == 1:
            result.scalar_one.return_value = 0
        else:
            result.scalars.return_value.all.return_value = []
        return result

    session.execute = _execute
    override_policy_session(app, session)

    rm_id = uuid.uuid4()
    resp = await client.get(
        f"/api/v1/policies?risk_model_id={rm_id}",
        headers=make_reviewer_headers(settings),
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


@pytest.mark.asyncio
async def test_create_policy(app, client, settings):
    rm_id = uuid.uuid4()
    policy = _make_policy(risk_model_id=rm_id)
    session = AsyncMock()
    call_count = 0

    async def _execute(stmt, *args, **kwargs):
        nonlocal call_count
        result = MagicMock()
        call_count += 1
        if call_count == 1:
            result.scalar_one_or_none.return_value = MagicMock(spec=RiskModel)
        return result

    async def _refresh(obj):
        obj.id = policy.id
        obj.is_active = policy.is_active
        obj.created_at = policy.created_at
        obj.updated_at = policy.updated_at
        obj.created_by = policy.created_by
        obj.description = policy.description

    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = _refresh
    session.execute = _execute
    override_policy_session(app, session)

    resp = await client.post(
        "/api/v1/policies",
        json={"risk_model_id": str(rm_id), "name": "New Policy"},
        headers=make_admin_headers(settings),
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_create_policy_risk_model_not_found(app, client, settings):
    session = AsyncMock()

    async def _execute(stmt, *args, **kwargs):
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        return result

    session.execute = _execute
    override_policy_session(app, session)

    resp = await client.post(
        "/api/v1/policies",
        json={"risk_model_id": str(uuid.uuid4()), "name": "X"},
        headers=make_admin_headers(settings),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_policy_duplicate_name(app, client, settings):
    from sqlalchemy.exc import IntegrityError

    session = AsyncMock()
    session.add = MagicMock()
    session.rollback = AsyncMock()
    call_count = 0

    async def _execute(stmt, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        if call_count == 1:
            result.scalar_one_or_none.return_value = MagicMock()
        return result

    session.execute = _execute
    session.commit = AsyncMock(side_effect=IntegrityError("", {}, None))
    override_policy_session(app, session)

    resp = await client.post(
        "/api/v1/policies",
        json={"risk_model_id": str(uuid.uuid4()), "name": "Dup"},
        headers=make_admin_headers(settings),
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_get_policy_detail(app, client, settings):
    policy = _make_policy()
    session = AsyncMock()
    call_count = 0

    async def _execute(stmt, *args, **kwargs):
        nonlocal call_count
        result = MagicMock()
        call_count += 1
        if call_count == 1:
            result.scalar_one_or_none.return_value = policy
        elif call_count == 2:
            result.scalar_one.return_value = "Risk Model A"
        elif call_count == 3:
            result.scalar_one.return_value = 4
        else:
            result.scalar_one.return_value = 1
        return result

    session.execute = _execute
    override_policy_session(app, session)

    resp = await client.get(f"/api/v1/policies/{policy.id}", headers=make_reviewer_headers(settings))
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_model_name"] == "Risk Model A"
    assert data["rule_count"] == 4


@pytest.mark.asyncio
async def test_update_policy(app, client, settings):
    policy = _make_policy(name="Old")
    session = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    async def _execute(stmt, *args, **kwargs):
        result = MagicMock()
        result.scalar_one_or_none.return_value = policy
        return result

    session.execute = _execute
    override_policy_session(app, session)

    resp = await client.patch(
        f"/api/v1/policies/{policy.id}",
        json={"name": "New"},
        headers=make_admin_headers(settings),
    )
    assert resp.status_code == 200
    assert policy.name == "New"


# --- Rule tests ---

@pytest.mark.asyncio
async def test_list_rules(app, client, settings):
    policy = _make_policy()
    rule = _make_rule(policy_id=policy.id)
    session = AsyncMock()
    call_count = 0

    async def _execute(stmt, *args, **kwargs):
        nonlocal call_count
        result = MagicMock()
        call_count += 1
        if call_count == 1:
            result.scalar_one_or_none.return_value = policy
        elif call_count == 2:
            result.scalar_one.return_value = 1
        else:
            result.scalars.return_value.all.return_value = [rule]
        return result

    session.execute = _execute
    override_policy_session(app, session)

    resp = await client.get(
        f"/api/v1/policies/{policy.id}/rules",
        headers=make_reviewer_headers(settings),
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


@pytest.mark.asyncio
async def test_create_rule(app, client, settings):
    policy = _make_policy()
    rule = _make_rule(policy_id=policy.id)
    session = AsyncMock()

    async def _execute(stmt, *args, **kwargs):
        result = MagicMock()
        result.scalar_one_or_none.return_value = policy
        return result

    async def _refresh(obj):
        obj.id = rule.id
        obj.is_active = rule.is_active
        obj.created_at = rule.created_at
        obj.updated_at = rule.updated_at
        obj.created_by = rule.created_by
        obj.description = rule.description

    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = _refresh
    session.execute = _execute
    override_policy_session(app, session)

    resp = await client.post(
        f"/api/v1/policies/{policy.id}/rules",
        json={"name": "Rule 1", "kql": "level:high", "severity": "high"},
        headers=make_admin_headers(settings),
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_create_rule_invalid_severity(app, client, settings):
    override_policy_session(app, AsyncMock())

    resp = await client.post(
        f"/api/v1/policies/{uuid.uuid4()}/rules",
        json={"name": "Rule", "kql": "x", "severity": "extreme"},
        headers=make_admin_headers(settings),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_rule_policy_not_found(app, client, settings):
    session = AsyncMock()

    async def _execute(stmt, *args, **kwargs):
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        return result

    session.execute = _execute
    override_policy_session(app, session)

    resp = await client.post(
        f"/api/v1/policies/{uuid.uuid4()}/rules",
        json={"name": "Rule", "kql": "x", "severity": "low"},
        headers=make_admin_headers(settings),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_rule(app, client, settings):
    rule = _make_rule()
    session = AsyncMock()

    async def _execute(stmt, *args, **kwargs):
        result = MagicMock()
        result.scalar_one_or_none.return_value = rule
        return result

    session.execute = _execute
    override_policy_session(app, session)

    resp = await client.get(f"/api/v1/rules/{rule.id}", headers=make_reviewer_headers(settings))
    assert resp.status_code == 200
    assert resp.json()["id"] == str(rule.id)


@pytest.mark.asyncio
async def test_update_rule(app, client, settings):
    rule = _make_rule(severity="low")
    session = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    async def _execute(stmt, *args, **kwargs):
        result = MagicMock()
        result.scalar_one_or_none.return_value = rule
        return result

    session.execute = _execute
    override_policy_session(app, session)

    resp = await client.patch(
        f"/api/v1/rules/{rule.id}",
        json={"severity": "critical"},
        headers=make_admin_headers(settings),
    )
    assert resp.status_code == 200
    assert rule.severity == "critical"


@pytest.mark.asyncio
async def test_delete_rule_soft(app, client, settings):
    rule = _make_rule(is_active=True)
    session = AsyncMock()
    session.commit = AsyncMock()

    async def _execute(stmt, *args, **kwargs):
        result = MagicMock()
        result.scalar_one_or_none.return_value = rule
        return result

    session.execute = _execute
    override_policy_session(app, session)

    resp = await client.delete(
        f"/api/v1/rules/{rule.id}",
        headers=make_admin_headers(settings),
    )
    assert resp.status_code == 204
    assert rule.is_active is False


# --- Group-policy tests ---

@pytest.mark.asyncio
async def test_list_group_policies(app, client, settings):
    policy = _make_policy()
    gp = _make_group_policy(policy_id=policy.id)
    session = AsyncMock()
    call_count = 0

    async def _execute(stmt, *args, **kwargs):
        nonlocal call_count
        result = MagicMock()
        call_count += 1
        if call_count == 1:
            result.scalar_one_or_none.return_value = policy
        else:
            result.scalars.return_value.all.return_value = [gp]
        return result

    session.execute = _execute
    override_policy_session(app, session)

    resp = await client.get(
        f"/api/v1/policies/{policy.id}/groups",
        headers=make_admin_headers(settings),
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_assign_group_policy(app, client, settings):
    policy = _make_policy()
    group_id = uuid.uuid4()
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    call_count = 0

    async def _execute(stmt, *args, **kwargs):
        nonlocal call_count
        result = MagicMock()
        call_count += 1
        result.scalar_one_or_none.return_value = MagicMock()
        return result

    session.execute = _execute
    override_policy_session(app, session)

    resp = await client.post(
        f"/api/v1/policies/{policy.id}/groups",
        json={"group_id": str(group_id)},
        headers=make_admin_headers(settings),
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_assign_group_policy_duplicate(app, client, settings):
    from sqlalchemy.exc import IntegrityError

    policy = _make_policy()
    session = AsyncMock()
    session.add = MagicMock()
    session.rollback = AsyncMock()
    session.commit = AsyncMock(side_effect=IntegrityError("", {}, None))

    async def _execute(stmt, *args, **kwargs):
        result = MagicMock()
        result.scalar_one_or_none.return_value = MagicMock()
        return result

    session.execute = _execute
    override_policy_session(app, session)

    resp = await client.post(
        f"/api/v1/policies/{policy.id}/groups",
        json={"group_id": str(uuid.uuid4())},
        headers=make_admin_headers(settings),
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_remove_group_policy(app, client, settings):
    policy_id = uuid.uuid4()
    group_id = uuid.uuid4()
    session = AsyncMock()
    session.commit = AsyncMock()

    async def _execute(stmt, *args, **kwargs):
        return MagicMock()

    session.execute = _execute
    override_policy_session(app, session)

    resp = await client.delete(
        f"/api/v1/policies/{policy_id}/groups/{group_id}",
        headers=make_admin_headers(settings),
    )
    assert resp.status_code == 204
