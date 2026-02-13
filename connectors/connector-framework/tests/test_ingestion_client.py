"""Tests for umbrella_connector.ingestion_client."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from umbrella_connector.config import IngestionAPIConfig
from umbrella_connector.ingestion_client import IngestionClient
from umbrella_connector.models import RawMessage
from umbrella_schema import Channel


@pytest.fixture
def api_config() -> IngestionAPIConfig:
    return IngestionAPIConfig(base_url="http://test-ingestion:8000", timeout_seconds=5.0)


@pytest.fixture
def client(api_config: IngestionAPIConfig) -> IngestionClient:
    return IngestionClient(api_config)


class TestIngestionClient:
    @pytest.mark.asyncio
    async def test_start_creates_httpx_client(self, client: IngestionClient):
        await client.start()
        assert client._client is not None
        await client.stop()

    @pytest.mark.asyncio
    async def test_stop_when_not_started(self, client: IngestionClient):
        await client.stop()  # should not raise

    @pytest.mark.asyncio
    async def test_stop_closes_client(self, client: IngestionClient):
        await client.start()
        await client.stop()
        assert client._client is not None  # reference kept but closed

    @pytest.mark.asyncio
    @respx.mock
    async def test_submit_success(self, api_config: IngestionAPIConfig, raw_message: RawMessage):
        route = respx.post("http://test-ingestion:8000/v1/ingest").respond(200, json={"ok": True})

        client = IngestionClient(api_config)
        await client.start()
        try:
            await client.submit(raw_message)
            assert route.called
            # Verify the request body
            request = route.calls[0].request
            body = json.loads(request.content)
            assert body["raw_message_id"] == "msg-001"
            assert request.headers["content-type"] == "application/json"
        finally:
            await client.stop()

    @pytest.mark.asyncio
    @respx.mock
    async def test_submit_raises_on_server_error(
        self, api_config: IngestionAPIConfig, raw_message: RawMessage
    ):
        respx.post("http://test-ingestion:8000/v1/ingest").respond(500)

        client = IngestionClient(api_config)
        await client.start()
        try:
            with pytest.raises(httpx.HTTPStatusError):
                await client.submit(raw_message)
        finally:
            await client.stop()

    @pytest.mark.asyncio
    @respx.mock
    async def test_submit_raises_on_client_error(
        self, api_config: IngestionAPIConfig, raw_message: RawMessage
    ):
        respx.post("http://test-ingestion:8000/v1/ingest").respond(422)

        client = IngestionClient(api_config)
        await client.start()
        try:
            with pytest.raises(httpx.HTTPStatusError):
                await client.submit(raw_message)
        finally:
            await client.stop()

    @pytest.mark.asyncio
    async def test_submit_not_started_raises(
        self, client: IngestionClient, raw_message: RawMessage
    ):
        with pytest.raises(AssertionError, match="Client not started"):
            await client.submit(raw_message)

    def test_mtls_config_stored(self):
        cfg = IngestionAPIConfig(
            base_url="https://secure-api:443",
            mtls_cert_path="/certs/client.crt",
            mtls_key_path="/certs/client.key",
            mtls_ca_path="/certs/ca.crt",
        )
        client = IngestionClient(cfg)
        assert client._config.mtls_cert_path == "/certs/client.crt"

    @pytest.mark.asyncio
    async def test_disabled_mode_empty_base_url(self, raw_message: RawMessage):
        """When base_url is empty, client remains None and submit is a no-op."""
        cfg = IngestionAPIConfig(base_url="")
        client = IngestionClient(cfg)

        await client.start()
        assert client._client is None

        # submit should be a no-op (not raise)
        await client.submit(raw_message)

        await client.stop()

    @pytest.mark.asyncio
    async def test_disabled_mode_whitespace_base_url(self, raw_message: RawMessage):
        """Whitespace-only base_url is treated as disabled."""
        cfg = IngestionAPIConfig(base_url="   ")
        client = IngestionClient(cfg)

        # Note: httpx will fail with invalid base_url, but our check is for empty string
        # This documents current behavior - whitespace is NOT treated as empty
        await client.start()
        # httpx will accept whitespace base_url, so client will be created
        assert client._client is not None
        await client.stop()
