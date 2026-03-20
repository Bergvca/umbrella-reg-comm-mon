"""Tests for the POST /api/v1/messages/nl-search endpoint."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import make_reviewer_headers, override_es


def _make_es_hit(doc_id="doc1", channel="email"):
    return {
        "_index": "messages-2024",
        "_id": doc_id,
        "_score": 1.5,
        "_source": {
            "message_id": doc_id,
            "channel": channel,
            "timestamp": "2024-01-01T00:00:00Z",
        },
        "highlight": {"body_text": ["<em>quarterly</em> earnings"]},
    }


SAMPLE_TRANSLATION = {
    "es_query": {
        "query": {
            "bool": {
                "must": [
                    {"multi_match": {"query": "quarterly earnings", "fields": ["body_text"]}}
                ],
                "filter": [
                    {"term": {"channel": "email"}},
                ],
            }
        },
        "sort": [{"timestamp": {"order": "desc"}}],
    },
    "explanation": "Searching for 'quarterly earnings' in emails.",
}


@pytest.mark.asyncio
async def test_nl_search_success(app, client, settings):
    es_mock = AsyncMock()
    es_mock.search = AsyncMock(return_value={
        "hits": {
            "total": {"value": 1},
            "hits": [_make_es_hit()],
        }
    })
    override_es(app, es_mock)

    headers = make_reviewer_headers(settings)

    with patch("umbrella_ui.routers.messages.httpx.AsyncClient") as MockClient:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = SAMPLE_TRANSLATION
        mock_resp.raise_for_status = MagicMock()

        mock_instance = AsyncMock()
        mock_instance.post = AsyncMock(return_value=mock_resp)
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_instance

        resp = await client.post(
            "/api/v1/messages/nl-search",
            json={"query": "emails about quarterly earnings"},
            headers=headers,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert len(data["hits"]) == 1
    assert "generated_query" in data
    assert "explanation" in data
    assert data["explanation"] == "Searching for 'quarterly earnings' in emails."


@pytest.mark.asyncio
async def test_nl_search_rejects_scripts(app, client, settings):
    es_mock = AsyncMock()
    override_es(app, es_mock)

    headers = make_reviewer_headers(settings)

    malicious_translation = {
        "es_query": {
            "query": {"script_score": {"query": {"match_all": {}}, "script": {"source": "1"}}},
        },
        "explanation": "Malicious query.",
    }

    with patch("umbrella_ui.routers.messages.httpx.AsyncClient") as MockClient:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = malicious_translation
        mock_resp.raise_for_status = MagicMock()

        mock_instance = AsyncMock()
        mock_instance.post = AsyncMock(return_value=mock_resp)
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_instance

        resp = await client.post(
            "/api/v1/messages/nl-search",
            json={"query": "test"},
            headers=headers,
        )

    assert resp.status_code == 422
    assert "forbidden" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_nl_search_offset_limit(app, client, settings):
    es_mock = AsyncMock()
    es_mock.search = AsyncMock(return_value={
        "hits": {"total": {"value": 0}, "hits": []}
    })
    override_es(app, es_mock)

    headers = make_reviewer_headers(settings)

    with patch("umbrella_ui.routers.messages.httpx.AsyncClient") as MockClient:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = SAMPLE_TRANSLATION
        mock_resp.raise_for_status = MagicMock()

        mock_instance = AsyncMock()
        mock_instance.post = AsyncMock(return_value=mock_resp)
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_instance

        resp = await client.post(
            "/api/v1/messages/nl-search",
            json={"query": "test", "offset": 40, "limit": 10},
            headers=headers,
        )

    assert resp.status_code == 200
    # Verify that from/size was injected into the ES query
    call_kwargs = es_mock.search.call_args
    body = call_kwargs.kwargs.get("body") or call_kwargs[1].get("body")
    assert body["from"] == 40
    assert body["size"] == 10


@pytest.mark.asyncio
async def test_nl_search_agent_runtime_unavailable(app, client, settings):
    es_mock = AsyncMock()
    override_es(app, es_mock)

    headers = make_reviewer_headers(settings)

    import httpx as real_httpx

    with patch("umbrella_ui.routers.messages.httpx.AsyncClient") as MockClient:
        mock_instance = AsyncMock()
        mock_instance.post = AsyncMock(side_effect=real_httpx.ConnectError("Connection refused"))
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_instance

        resp = await client.post(
            "/api/v1/messages/nl-search",
            json={"query": "test"},
            headers=headers,
        )

    assert resp.status_code == 502
    assert "unreachable" in resp.json()["detail"].lower()
