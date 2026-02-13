"""Async HTTP client for the ingestion API with optional mTLS."""

from __future__ import annotations

import ssl

import httpx
import structlog

from .config import IngestionAPIConfig
from .models import RawMessage

logger = structlog.get_logger()


class IngestionClient:
    """Delivers :class:`RawMessage` payloads to the ingestion API over HTTP.

    Supports mTLS when certificate paths are configured.
    """

    def __init__(self, config: IngestionAPIConfig) -> None:
        self._config = config
        self._client: httpx.AsyncClient | None = None
        self._started = False

    async def start(self) -> None:
        self._started = True

        # Skip client creation if base_url is empty (disabled mode)
        if not self._config.base_url:
            logger.info("ingestion_client_disabled", reason="empty_base_url")
            return

        ssl_context: ssl.SSLContext | bool = False  # no TLS verification by default

        if self._config.mtls_cert_path and self._config.mtls_key_path:
            ssl_context = ssl.create_default_context(
                cafile=self._config.mtls_ca_path,
            )
            ssl_context.load_cert_chain(
                certfile=self._config.mtls_cert_path,
                keyfile=self._config.mtls_key_path,
            )

        self._client = httpx.AsyncClient(
            base_url=self._config.base_url,
            timeout=httpx.Timeout(self._config.timeout_seconds),
            verify=ssl_context,
        )
        logger.info("ingestion_client_started", base_url=self._config.base_url)

    async def stop(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            logger.info("ingestion_client_stopped")

    async def submit(self, message: RawMessage) -> None:
        """POST a raw message to the ingestion API.

        If the client is disabled (base_url was empty), this is a no-op.
        Raises :class:`httpx.HTTPStatusError` on non-2xx responses.
        """
        if not self._started:
            raise AssertionError("Client not started")

        if self._client is None:
            return  # disabled

        response = await self._client.post(
            "/v1/ingest",
            content=message.model_dump_json(),
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        logger.debug(
            "message_submitted",
            raw_message_id=message.raw_message_id,
            status_code=response.status_code,
        )
