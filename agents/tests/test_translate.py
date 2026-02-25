"""Tests for the /translate-query endpoint."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from umbrella_agents.app import create_app
from umbrella_agents.config import Settings


def _make_settings(**overrides) -> Settings:
    defaults = {
        "database_url": "sqlite+aiosqlite://",
        "elasticsearch_url": "http://localhost:9200",
    }
    defaults.update(overrides)
    return Settings(**defaults)


@pytest.fixture
def settings():
    return _make_settings()


@pytest.fixture
def app(settings):
    return create_app(settings)


@pytest.fixture
async def client(app):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


def _mock_db_no_models(app):
    """Set up app.state.db with a session that returns no models."""
    mock_db = MagicMock()
    session = AsyncMock()

    async def _execute(stmt, *args, **kwargs):
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        return result

    session.execute = _execute

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _session_factory():
        yield session

    mock_db.session_factory = _session_factory
    app.state.db = mock_db


SAMPLE_RESPONSE = {
    "es_query": {
        "query": {
            "bool": {
                "must": [
                    {"multi_match": {"query": "quarterly earnings", "fields": ["body_text", "transcript"]}}
                ],
                "filter": [
                    {"term": {"channel": "email"}},
                    {"range": {"timestamp": {"gte": "now-1w"}}},
                ],
            }
        },
        "highlight": {"fields": {"body_text": {}, "transcript": {}}},
        "sort": [{"timestamp": {"order": "desc"}}],
    },
    "explanation": "Searching for 'quarterly earnings' in emails from the last week.",
}


@pytest.mark.asyncio
async def test_translate_query_success(app, client):
    _mock_db_no_models(app)

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps(SAMPLE_RESPONSE)

    with patch("umbrella_agents.model_router.acompletion", new_callable=AsyncMock, return_value=mock_response):
        resp = await client.post("/translate-query", json={
            "natural_language_query": "emails about quarterly earnings from last week",
        })

    assert resp.status_code == 200
    data = resp.json()
    assert "es_query" in data
    assert "explanation" in data
    assert data["es_query"]["query"]["bool"]["must"][0]["multi_match"]["query"] == "quarterly earnings"


@pytest.mark.asyncio
async def test_translate_query_includes_field_schema_in_prompt(app, client):
    _mock_db_no_models(app)

    captured_messages = []

    async def mock_acompletion(**kwargs):
        captured_messages.extend(kwargs.get("messages", []))
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = json.dumps(SAMPLE_RESPONSE)
        return mock_resp

    with patch("umbrella_agents.model_router.acompletion", side_effect=mock_acompletion):
        resp = await client.post("/translate-query", json={
            "natural_language_query": "test query",
            "field_schema": {"body_text": "text", "channel": "keyword"},
        })

    assert resp.status_code == 200
    # The user message should contain the field schema
    user_msg = next(m for m in captured_messages if m["role"] == "user")
    assert "body_text" in user_msg["content"]
    assert "keyword" in user_msg["content"]


@pytest.mark.asyncio
async def test_translate_query_invalid_llm_response(app, client):
    _mock_db_no_models(app)

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = '{"not_es_query": {}}'

    with patch("umbrella_agents.model_router.acompletion", new_callable=AsyncMock, return_value=mock_response):
        resp = await client.post("/translate-query", json={
            "natural_language_query": "test query",
        })

    assert resp.status_code == 422
    assert "Translation failed" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_translate_query_llm_timeout(app, client):
    _mock_db_no_models(app)

    with patch("umbrella_agents.model_router.acompletion", new_callable=AsyncMock, side_effect=TimeoutError("LLM timeout")):
        resp = await client.post("/translate-query", json={
            "natural_language_query": "test query",
        })

    assert resp.status_code == 502
    assert "unavailable" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_health_endpoint(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "umbrella-agents"
