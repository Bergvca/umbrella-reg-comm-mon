"""Entity resolver — maps participant handles to entity IDs using an in-memory cache."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import asyncpg
import structlog

from umbrella_schema.normalized_message import Channel, NormalizedMessage

logger = structlog.get_logger()

# Map channels to handle types for resolution
_CHANNEL_HANDLE_TYPE: dict[Channel, str] = {
    Channel.EMAIL: "email",
    Channel.BLOOMBERG_EMAIL: "email",
    Channel.TEAMS_CHAT: "teams_id",
    Channel.TEAMS_CALLS: "teams_id",
    Channel.BLOOMBERG_CHAT: "bloomberg_uuid",
    Channel.UNIGY_TURRET: "turret_extension",
}


@dataclass(frozen=True, slots=True)
class ResolvedEntity:
    id: str
    display_name: str


class EntityResolver:
    """Resolve participant handles to entity IDs.

    Loads the full handle→entity map from Postgres on startup, then
    periodically refreshes in the background.
    """

    def __init__(self, dsn: str, refresh_interval: int = 60) -> None:
        self._dsn = dsn
        self._refresh_interval = refresh_interval
        self._cache: dict[tuple[str, str], ResolvedEntity] = {}
        self._pool: asyncpg.Pool | None = None
        self._refresh_task: asyncio.Task | None = None

    async def start(self) -> None:
        """Connect to Postgres, load cache, start background refresh."""
        self._pool = await asyncpg.create_pool(self._dsn, min_size=1, max_size=2)
        await self._load_cache()
        self._refresh_task = asyncio.create_task(self._refresh_loop())
        logger.info("entity_resolver_started", cache_size=len(self._cache))

    async def stop(self) -> None:
        """Cancel background refresh and close pool."""
        if self._refresh_task:
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass
        if self._pool:
            await self._pool.close()
        logger.info("entity_resolver_stopped")

    async def resolve(self, message: NormalizedMessage) -> NormalizedMessage:
        """Enrich participants with entity_id and entity_name where a match exists."""
        channel = message.channel
        for participant in message.participants:
            handle_type, handle_value = self._normalize_handle(participant.id, channel)
            entity = self._cache.get((handle_type, handle_value))
            if entity:
                participant.entity_id = entity.id
                participant.entity_name = entity.display_name
        return message

    def _normalize_handle(self, handle: str, channel: Channel) -> tuple[str, str]:
        """Normalize handle value and infer handle_type from channel."""
        handle_type = _CHANNEL_HANDLE_TYPE.get(channel, "email")
        handle_value = handle.strip()
        if handle_type == "email":
            handle_value = handle_value.lower()
        return handle_type, handle_value

    async def _load_cache(self) -> None:
        """Load the full handle→entity mapping from Postgres."""
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT h.handle_type, h.handle_value, e.id::text, e.display_name
                FROM entity.handles h
                JOIN entity.entities e ON e.id = h.entity_id
                """
            )
        new_cache: dict[tuple[str, str], ResolvedEntity] = {}
        for row in rows:
            key = (row["handle_type"], row["handle_value"])
            new_cache[key] = ResolvedEntity(id=row["id"], display_name=row["display_name"])
        self._cache = new_cache

    async def _refresh_loop(self) -> None:
        """Periodically reload the cache."""
        while True:
            await asyncio.sleep(self._refresh_interval)
            try:
                await self._load_cache()
                logger.debug("entity_cache_refreshed", cache_size=len(self._cache))
            except Exception:
                logger.exception("entity_cache_refresh_failed")
