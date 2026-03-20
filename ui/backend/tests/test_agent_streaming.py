"""Tests for the agent streaming proxy endpoints."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from tests.conftest import (
    make_reviewer_headers,
    make_supervisor_headers,
    override_agent_session,
)


# ---------------------------------------------------------------------------
# POST /api/v1/agent-runs/stream
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_stream_proxies_to_runtime(app, client, settings):
    session = AsyncMock()
    override_agent_session(app, session)
    headers = make_reviewer_headers(settings)

    agent_id = str(uuid.uuid4())
    runtime_response = {"run_id": str(uuid.uuid4()), "status": "running"}

    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.json.return_value = runtime_response
    mock_resp.raise_for_status = MagicMock()

    with patch("umbrella_ui.routers.agent_runs.httpx.AsyncClient") as MockClient:
        mock_instance = AsyncMock()
        mock_instance.post = AsyncMock(return_value=mock_resp)
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_instance

        resp = await client.post(
            "/api/v1/agent-runs/stream",
            json={"agent_id": agent_id, "input": "test prompt"},
            headers=headers,
        )

    assert resp.status_code == 201
    body = resp.json()
    assert body["run_id"] == runtime_response["run_id"]
    assert body["status"] == "running"


@pytest.mark.asyncio
async def test_execute_stream_runtime_error(app, client, settings):
    session = AsyncMock()
    override_agent_session(app, session)
    headers = make_reviewer_headers(settings)

    with patch("umbrella_ui.routers.agent_runs.httpx.AsyncClient") as MockClient:
        mock_instance = AsyncMock()
        mock_instance.post = AsyncMock(
            side_effect=httpx.RequestError("unreachable")
        )
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_instance

        resp = await client.post(
            "/api/v1/agent-runs/stream",
            json={"agent_id": str(uuid.uuid4()), "input": "test"},
            headers=headers,
        )

    assert resp.status_code == 502


# ---------------------------------------------------------------------------
# POST /api/v1/agent-runs/{run_id}/cancel
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancel_run_proxies_to_runtime(app, client, settings):
    session = AsyncMock()
    override_agent_session(app, session)
    headers = make_supervisor_headers(settings)

    run_id = str(uuid.uuid4())
    runtime_response = {"status": "cancelling"}

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = runtime_response
    mock_resp.raise_for_status = MagicMock()

    with patch("umbrella_ui.routers.agent_runs.httpx.AsyncClient") as MockClient:
        mock_instance = AsyncMock()
        mock_instance.post = AsyncMock(return_value=mock_resp)
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_instance

        resp = await client.post(
            f"/api/v1/agent-runs/{run_id}/cancel",
            headers=headers,
        )

    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelling"


@pytest.mark.asyncio
async def test_cancel_run_requires_supervisor(app, client, settings):
    session = AsyncMock()
    override_agent_session(app, session)
    headers = make_reviewer_headers(settings)

    run_id = str(uuid.uuid4())
    resp = await client.post(
        f"/api/v1/agent-runs/{run_id}/cancel",
        headers=headers,
    )

    assert resp.status_code == 403
