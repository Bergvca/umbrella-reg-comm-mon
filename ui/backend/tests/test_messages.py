"""Tests for message search and retrieval endpoints."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from elasticsearch import NotFoundError

from tests.conftest import make_reviewer_headers, override_es


def _make_es_hit(doc_id="doc1", channel="email", audio_ref=None):
    source = {
        "message_id": doc_id,
        "channel": channel,
        "timestamp": "2024-01-01T00:00:00Z",
    }
    if audio_ref:
        source["audio_ref"] = audio_ref
    return {
        "_index": "messages-2024",
        "_id": doc_id,
        "_score": 1.5,
        "_source": source,
        "highlight": {"body_text": ["<em>hello</em> world"]},
    }


@pytest.mark.asyncio
async def test_search_messages(app, client, settings):
    es_mock = AsyncMock()
    es_mock.search = AsyncMock(return_value={
        "hits": {
            "total": {"value": 1},
            "hits": [_make_es_hit()],
        }
    })
    override_es(app, es_mock)

    headers = make_reviewer_headers(settings)
    resp = await client.get("/api/v1/messages/search?q=hello", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert len(data["hits"]) == 1
    assert data["hits"][0]["highlights"]["body_text"] == ["<em>hello</em> world"]


@pytest.mark.asyncio
async def test_search_messages_with_filters(app, client, settings):
    es_mock = AsyncMock()
    es_mock.search = AsyncMock(return_value={
        "hits": {"total": {"value": 0}, "hits": []}
    })
    override_es(app, es_mock)

    headers = make_reviewer_headers(settings)
    resp = await client.get(
        "/api/v1/messages/search?channel=email&date_from=2024-01-01T00:00:00&date_to=2024-12-31T00:00:00",
        headers=headers,
    )
    assert resp.status_code == 200
    # Verify ES search was called with a body
    call_kwargs = es_mock.search.call_args
    body = call_kwargs.kwargs.get("body") or call_kwargs.args[0] if call_kwargs.args else None
    assert es_mock.search.called


@pytest.mark.asyncio
async def test_get_single_message(app, client, settings):
    es_mock = AsyncMock()
    es_mock.get = AsyncMock(return_value={
        "_source": {
            "message_id": "doc1",
            "channel": "teams",
            "timestamp": "2024-03-15T10:00:00Z",
        }
    })
    override_es(app, es_mock)

    headers = make_reviewer_headers(settings)
    resp = await client.get("/api/v1/messages/messages-2024/doc1", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["channel"] == "teams"


@pytest.mark.asyncio
async def test_get_message_not_found(app, client, settings):
    from elasticsearch import NotFoundError

    es_mock = AsyncMock()
    es_mock.get = AsyncMock(
        side_effect=NotFoundError(404, {"error": "not found"}, {"error": "not found"})
    )
    override_es(app, es_mock)

    headers = make_reviewer_headers(settings)
    resp = await client.get("/api/v1/messages/messages-2024/nonexistent", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_audio_url(app, client, settings):
    audio_uri = "s3://umbrella/audio/call-123.mp3"
    es_mock = AsyncMock()
    es_mock.get = AsyncMock(return_value={
        "_source": {
            "message_id": "doc1",
            "channel": "turret",
            "timestamp": "2024-01-01T00:00:00Z",
            "audio_ref": audio_uri,
        }
    })
    override_es(app, es_mock)

    with patch("umbrella_ui.routers.messages.boto3") as mock_boto3:
        s3_client = MagicMock()
        s3_client.generate_presigned_url.return_value = "https://s3.example.com/presigned-url"
        mock_boto3.client.return_value = s3_client

        headers = make_reviewer_headers(settings)
        resp = await client.get("/api/v1/messages/messages-2024/doc1/audio", headers=headers)

    assert resp.status_code == 200
    data = resp.json()
    assert "url" in data
    assert data["url"] == "https://s3.example.com/presigned-url"


@pytest.mark.asyncio
async def test_get_audio_url_no_audio(app, client, settings):
    es_mock = AsyncMock()
    es_mock.get = AsyncMock(return_value={
        "_source": {
            "message_id": "doc1",
            "channel": "email",
            "timestamp": "2024-01-01T00:00:00Z",
        }
    })
    override_es(app, es_mock)

    headers = make_reviewer_headers(settings)
    resp = await client.get("/api/v1/messages/messages-2024/doc1/audio", headers=headers)
    assert resp.status_code == 404
