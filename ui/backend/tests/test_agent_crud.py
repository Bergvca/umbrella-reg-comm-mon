"""Tests for agent CRUD, agent-models, agent-tools, and agent-runs endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import (
    make_admin_headers,
    make_reviewer_headers,
    make_supervisor_headers,
    override_agent_session,
    override_es,
)


def _make_model_row(**overrides):
    m = MagicMock()
    m.id = overrides.get("id", uuid.uuid4())
    m.name = overrides.get("name", "GPT-4o")
    m.provider = overrides.get("provider", "openai")
    m.model_id = overrides.get("model_id", "gpt-4o")
    m.base_url = overrides.get("base_url", None)
    m.api_key_secret = None
    m.max_tokens = overrides.get("max_tokens", 4096)
    m.is_active = overrides.get("is_active", True)
    m.created_by = overrides.get("created_by", uuid.uuid4())
    m.created_at = datetime.now(timezone.utc)
    m.updated_at = datetime.now(timezone.utc)
    return m


def _make_agent_row(model=None, **overrides):
    if model is None:
        model = _make_model_row()

    tool = MagicMock()
    tool.id = uuid.uuid4()
    tool.name = "es_search"
    tool.display_name = "ES Search"

    tool_link = MagicMock()
    tool_link.tool = tool
    tool_link.tool_config = None

    ds = MagicMock()
    ds.source_type = "elasticsearch"
    ds.source_identifier = "messages-*"

    a = MagicMock()
    a.id = overrides.get("id", uuid.uuid4())
    a.name = overrides.get("name", "Test Agent")
    a.description = overrides.get("description", "A test agent")
    a.model_id = model.id
    a.model_ref = model
    a.system_prompt = "You are a test agent."
    a.temperature = Decimal("0.00")
    a.max_iterations = 10
    a.output_schema = None
    a.tool_links = [tool_link]
    a.data_sources = [ds]
    a.is_builtin = False
    a.is_active = True
    a.created_by = uuid.uuid4()
    a.created_at = datetime.now(timezone.utc)
    a.updated_at = datetime.now(timezone.utc)
    return a


def _make_run_row(**overrides):
    r = MagicMock()
    r.id = overrides.get("id", uuid.uuid4())
    r.agent_id = overrides.get("agent_id", uuid.uuid4())
    r.status = overrides.get("status", "completed")
    r.input = {"prompt": "test"}
    r.output = {"response": "done"}
    r.error_message = None
    r.token_usage = None
    r.iterations = 3
    r.duration_ms = 1500
    r.triggered_by = uuid.uuid4()
    r.created_at = datetime.now(timezone.utc)
    r.completed_at = datetime.now(timezone.utc)
    r.steps = []
    return r


# ── Agent Models ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_agent_models(app, client, settings):
    model = _make_model_row()
    session = AsyncMock()

    async def _execute(stmt, *args, **kwargs):
        result = MagicMock()
        result.scalar_one.return_value = 1
        result.scalars.return_value.all.return_value = [model]
        return result

    session.execute = _execute
    override_agent_session(app, session)

    headers = make_supervisor_headers(settings)
    resp = await client.get("/api/v1/agent-models", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["name"] == "GPT-4o"


@pytest.mark.asyncio
async def test_create_agent_model(app, client, settings):
    model = _make_model_row(name="Claude Sonnet")
    session = AsyncMock()

    async def _execute(stmt, *args, **kwargs):
        result = MagicMock()
        return result

    session.execute = _execute
    session.add = MagicMock()
    session.commit = AsyncMock()

    async def _refresh(obj, **kw):
        obj.id = model.id
        obj.name = "Claude Sonnet"
        obj.provider = "anthropic"
        obj.model_id = "claude-sonnet-4-20250514"
        obj.base_url = None
        obj.max_tokens = 4096
        obj.is_active = True
        obj.created_by = uuid.uuid4()
        obj.created_at = datetime.now(timezone.utc)
        obj.updated_at = datetime.now(timezone.utc)

    session.refresh = _refresh
    override_agent_session(app, session)

    headers = make_admin_headers(settings)
    resp = await client.post("/api/v1/agent-models", json={
        "name": "Claude Sonnet",
        "provider": "anthropic",
        "model_id": "claude-sonnet-4-20250514",
    }, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Claude Sonnet"


# ── Agent Tools ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_agent_tools(app, client, settings):
    tool = MagicMock()
    tool.id = uuid.uuid4()
    tool.name = "es_search"
    tool.display_name = "ES Search"
    tool.description = "Search Elasticsearch"
    tool.category = "builtin"
    tool.parameters_schema = {"type": "object"}
    tool.is_active = True
    tool.created_at = datetime.now(timezone.utc)

    session = AsyncMock()

    async def _execute(stmt, *args, **kwargs):
        result = MagicMock()
        result.scalar_one.return_value = 1
        result.scalars.return_value.all.return_value = [tool]
        return result

    session.execute = _execute
    override_agent_session(app, session)

    headers = make_supervisor_headers(settings)
    resp = await client.get("/api/v1/agent-tools", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["name"] == "es_search"


# ── Agents CRUD ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_agents(app, client, settings):
    agent = _make_agent_row()
    session = AsyncMock()

    async def _execute(stmt, *args, **kwargs):
        result = MagicMock()
        result.scalar_one.return_value = 1
        result.scalars.return_value.all.return_value = [agent]
        return result

    session.execute = _execute
    override_agent_session(app, session)

    headers = make_reviewer_headers(settings)
    resp = await client.get("/api/v1/agents", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["name"] == "Test Agent"
    assert data["items"][0]["model"]["name"] == "GPT-4o"
    assert len(data["items"][0]["tools"]) == 1


@pytest.mark.asyncio
async def test_get_agent(app, client, settings):
    agent = _make_agent_row()
    session = AsyncMock()

    async def _execute(stmt, *args, **kwargs):
        result = MagicMock()
        result.scalar_one_or_none.return_value = agent
        return result

    session.execute = _execute
    override_agent_session(app, session)

    headers = make_reviewer_headers(settings)
    resp = await client.get(f"/api/v1/agents/{agent.id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Test Agent"


@pytest.mark.asyncio
async def test_get_agent_not_found(app, client, settings):
    session = AsyncMock()

    async def _execute(stmt, *args, **kwargs):
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        return result

    session.execute = _execute
    override_agent_session(app, session)

    headers = make_reviewer_headers(settings)
    resp = await client.get(f"/api/v1/agents/{uuid.uuid4()}", headers=headers)
    assert resp.status_code == 404


# ── Agent Create ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_agent(app, client, settings):
    """Create returns full agent with nested tool relationships."""
    model = _make_model_row()
    agent = _make_agent_row(model=model)
    session = AsyncMock()

    call_count = 0

    async def _execute(stmt, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        # After commit, the re-query returns the full agent
        result.scalar_one.return_value = agent
        return result

    session.execute = _execute
    session.add = MagicMock()
    session.commit = AsyncMock()
    override_agent_session(app, session)

    headers = make_supervisor_headers(settings)
    resp = await client.post("/api/v1/agents", json={
        "name": "Test Agent",
        "description": "A test agent",
        "model_id": str(model.id),
        "system_prompt": "You are a test agent.",
        "tool_ids": [],
        "data_sources": [
            {"source_type": "elasticsearch", "source_identifier": "messages-*"},
        ],
    }, headers=headers)

    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Test Agent"
    assert data["model"]["name"] == "GPT-4o"
    assert len(data["tools"]) == 1
    assert data["tools"][0]["name"] == "es_search"
    assert len(data["data_sources"]) == 1
    assert data["data_sources"][0]["source_type"] == "elasticsearch"


# ── Agent Update ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_agent(app, client, settings):
    """Update returns full agent with nested tool relationships after re-query."""
    model = _make_model_row()
    agent = _make_agent_row(model=model)
    agent_id = agent.id

    # After update, agent has a new data source
    updated_ds = MagicMock()
    updated_ds.source_type = "postgresql"
    updated_ds.source_identifier = "alert.alerts"

    updated_agent = _make_agent_row(model=model, id=agent_id, name="Updated Agent")
    updated_agent.data_sources = [updated_ds]

    session = AsyncMock()
    call_count = 0

    async def _execute(stmt, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        if call_count == 1:
            # First call: initial load of agent for update
            result.scalar_one_or_none.return_value = agent
        else:
            # Second call: re-query after commit with eager loads
            result.scalar_one.return_value = updated_agent
        return result

    session.execute = _execute
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.delete = AsyncMock()
    session.flush = AsyncMock()
    override_agent_session(app, session)

    headers = make_supervisor_headers(settings)
    resp = await client.put(f"/api/v1/agents/{agent_id}", json={
        "name": "Updated Agent",
        "data_sources": [
            {"source_type": "postgresql", "source_identifier": "alert.alerts"},
        ],
    }, headers=headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Updated Agent"
    assert data["model"]["name"] == "GPT-4o"
    assert len(data["tools"]) == 1
    assert data["tools"][0]["name"] == "es_search"
    assert len(data["data_sources"]) == 1
    assert data["data_sources"][0]["source_type"] == "postgresql"
    assert data["data_sources"][0]["source_identifier"] == "alert.alerts"


@pytest.mark.asyncio
async def test_update_agent_sets_naive_updated_at(app, client, settings):
    """Regression: updated_at must be tz-naive to match TIMESTAMP WITHOUT TIME ZONE columns."""
    model = _make_model_row()
    agent = _make_agent_row(model=model)
    agent_id = agent.id

    session = AsyncMock()
    call_count = 0

    async def _execute(stmt, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        if call_count == 1:
            result.scalar_one_or_none.return_value = agent
        else:
            result.scalar_one.return_value = agent
        return result

    session.execute = _execute
    session.commit = AsyncMock()
    override_agent_session(app, session)

    headers = make_supervisor_headers(settings)
    resp = await client.put(f"/api/v1/agents/{agent_id}", json={
        "name": "Renamed",
    }, headers=headers)

    assert resp.status_code == 200
    # The updated_at assigned to the ORM object must be timezone-naive
    assert agent.updated_at.tzinfo is None, (
        f"updated_at should be tz-naive but got tzinfo={agent.updated_at.tzinfo}"
    )


@pytest.mark.asyncio
async def test_update_agent_not_found(app, client, settings):
    session = AsyncMock()

    async def _execute(stmt, *args, **kwargs):
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        return result

    session.execute = _execute
    override_agent_session(app, session)

    headers = make_supervisor_headers(settings)
    resp = await client.put(f"/api/v1/agents/{uuid.uuid4()}", json={
        "name": "Nope",
    }, headers=headers)
    assert resp.status_code == 404


# ── Agent Runs ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_runs(app, client, settings):
    run = _make_run_row()
    session = AsyncMock()

    async def _execute(stmt, *args, **kwargs):
        result = MagicMock()
        result.scalar_one.return_value = 1
        result.scalars.return_value.all.return_value = [run]
        return result

    session.execute = _execute
    override_agent_session(app, session)

    headers = make_reviewer_headers(settings)
    resp = await client.get("/api/v1/agent-runs", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["status"] == "completed"


@pytest.mark.asyncio
async def test_get_run_detail(app, client, settings):
    step = MagicMock()
    step.id = uuid.uuid4()
    step.step_order = 1
    step.step_type = "llm_call"
    step.tool_name = None
    step.input = {"type": "llm_call"}
    step.output = {"response": "thinking..."}
    step.token_usage = None
    step.duration_ms = 200
    step.created_at = datetime.now(timezone.utc)

    run = _make_run_row()
    run.steps = [step]

    session = AsyncMock()

    async def _execute(stmt, *args, **kwargs):
        result = MagicMock()
        result.scalar_one_or_none.return_value = run
        return result

    session.execute = _execute
    override_agent_session(app, session)

    headers = make_reviewer_headers(settings)
    resp = await client.get(f"/api/v1/agent-runs/{run.id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert len(data["steps"]) == 1
    assert data["steps"][0]["step_type"] == "llm_call"


@pytest.mark.asyncio
async def test_execute_agent_run_runtime_unavailable(app, client, settings):
    session = AsyncMock()
    override_agent_session(app, session)

    import httpx as real_httpx

    with patch("umbrella_ui.routers.agent_runs.httpx.AsyncClient") as MockClient:
        mock_instance = AsyncMock()
        mock_instance.post = AsyncMock(side_effect=real_httpx.ConnectError("refused"))
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_instance

        headers = make_reviewer_headers(settings)
        resp = await client.post("/api/v1/agent-runs", json={
            "agent_id": str(uuid.uuid4()),
            "input": "test prompt",
        }, headers=headers)

    assert resp.status_code == 502
    assert "unreachable" in resp.json()["detail"].lower()
