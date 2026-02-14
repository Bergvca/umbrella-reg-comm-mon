"""Async Elasticsearch client wrapper."""

from __future__ import annotations

from elasticsearch import AsyncElasticsearch

from umbrella_ui.config import Settings


class ESClient:
    """Wraps the async Elasticsearch client.

    Created once at startup and stored on ``app.state``.
    """

    def __init__(self, settings: Settings) -> None:
        self._client = AsyncElasticsearch(
            hosts=[settings.elasticsearch_url],
            request_timeout=30,
        )

    @property
    def client(self) -> AsyncElasticsearch:
        return self._client

    async def close(self) -> None:
        await self._client.close()
