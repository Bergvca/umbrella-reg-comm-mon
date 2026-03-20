"""Tests for GET /api/v1/agent-data-sources/options."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from tests.conftest import (
    make_reviewer_headers,
    make_supervisor_headers,
    override_es,
)


@pytest.mark.asyncio
async def test_returns_indices_and_tables(app, client, settings):
    """Endpoint returns ES indices (with aliases) and safe PG tables."""
    es_mock = AsyncMock()
    es_mock.cat.indices = AsyncMock(return_value=[
        {"index": "messages-2026.01"},
        {"index": "messages-2026.02"},
        {"index": "alerts-2026.01"},
    ])
    override_es(app, es_mock)

    headers = make_supervisor_headers(settings)
    resp = await client.get("/api/v1/agent-data-sources/options", headers=headers)

    assert resp.status_code == 200
    data = resp.json()

    # Well-known aliases come first, then sorted real indices
    assert data["elasticsearch_indices"][0] == "messages"
    assert data["elasticsearch_indices"][1] == "alerts"
    assert "messages-2026.01" in data["elasticsearch_indices"]
    assert "messages-2026.02" in data["elasticsearch_indices"]
    assert "alerts-2026.01" in data["elasticsearch_indices"]

    # PG tables must include safe schemas only
    tables = data["postgresql_tables"]
    assert "alert.alerts" in tables
    assert "entity.entities" in tables
    assert "review.queues" in tables
    # Must not include unsafe schemas
    for t in tables:
        assert not t.startswith("iam.")
        assert not t.startswith("agent.")
        assert not t.startswith("policy.")


@pytest.mark.asyncio
async def test_filters_system_indices(app, client, settings):
    """ES system indices (starting with '.') are excluded."""
    es_mock = AsyncMock()
    es_mock.cat.indices = AsyncMock(return_value=[
        {"index": ".kibana_1"},
        {"index": ".security-7"},
        {"index": "messages-2026.01"},
    ])
    override_es(app, es_mock)

    headers = make_supervisor_headers(settings)
    resp = await client.get("/api/v1/agent-data-sources/options", headers=headers)

    assert resp.status_code == 200
    indices = resp.json()["elasticsearch_indices"]
    assert ".kibana_1" not in indices
    assert ".security-7" not in indices
    assert "messages-2026.01" in indices


@pytest.mark.asyncio
async def test_es_failure_returns_aliases_only(app, client, settings):
    """If ES cat.indices fails, endpoint still returns aliases and PG tables."""
    es_mock = AsyncMock()
    es_mock.cat.indices = AsyncMock(side_effect=Exception("connection refused"))
    override_es(app, es_mock)

    headers = make_supervisor_headers(settings)
    resp = await client.get("/api/v1/agent-data-sources/options", headers=headers)

    assert resp.status_code == 200
    data = resp.json()
    # Falls back to well-known aliases
    assert data["elasticsearch_indices"] == ["messages", "alerts"]
    # PG tables still returned
    assert len(data["postgresql_tables"]) > 0


@pytest.mark.asyncio
async def test_deduplicates_alias_names(app, client, settings):
    """If a real index matches a well-known alias name, no duplicates."""
    es_mock = AsyncMock()
    es_mock.cat.indices = AsyncMock(return_value=[
        {"index": "messages"},
        {"index": "alerts"},
        {"index": "other-index"},
    ])
    override_es(app, es_mock)

    headers = make_supervisor_headers(settings)
    resp = await client.get("/api/v1/agent-data-sources/options", headers=headers)

    assert resp.status_code == 200
    indices = resp.json()["elasticsearch_indices"]
    assert indices.count("messages") == 1
    assert indices.count("alerts") == 1
    assert "other-index" in indices


@pytest.mark.asyncio
async def test_requires_supervisor_role(app, client, settings):
    """Reviewer role is insufficient — should get 403."""
    es_mock = AsyncMock()
    es_mock.cat.indices = AsyncMock(return_value=[])
    override_es(app, es_mock)

    headers = make_reviewer_headers(settings)
    resp = await client.get("/api/v1/agent-data-sources/options", headers=headers)

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_unauthenticated_returns_401(app, client):
    """No auth header should get 401."""
    es_mock = AsyncMock()
    override_es(app, es_mock)

    resp = await client.get("/api/v1/agent-data-sources/options")

    assert resp.status_code == 401
