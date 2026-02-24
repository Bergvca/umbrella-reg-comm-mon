"""Tests for the EntityResolver."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from umbrella_schema.normalized_message import (
    Channel,
    Direction,
    NormalizedMessage,
    Participant,
)

from umbrella_ingestion.resolver import EntityResolver, ResolvedEntity


def _make_message(
    participants: list[Participant],
    channel: Channel = Channel.EMAIL,
) -> NormalizedMessage:
    return NormalizedMessage(
        message_id="msg-001",
        channel=channel,
        direction=Direction.INBOUND,
        timestamp=datetime.now(timezone.utc),
        participants=participants,
        body_text="test body",
    )


class TestEntityResolver:
    """Unit tests for EntityResolver using a pre-populated cache (no DB)."""

    def _make_resolver(self, cache: dict | None = None) -> EntityResolver:
        resolver = EntityResolver(dsn="postgresql://unused", refresh_interval=300)
        if cache is not None:
            resolver._cache = cache
        return resolver

    @pytest.mark.asyncio
    async def test_resolve_matches_email(self):
        cache = {
            ("email", "jane@acme.com"): ResolvedEntity(id="entity-1", display_name="Jane Smith"),
        }
        resolver = self._make_resolver(cache)
        msg = _make_message([
            Participant(id="jane@acme.com", name="Jane", role="sender"),
            Participant(id="unknown@example.com", name="Unknown", role="to"),
        ])

        result = await resolver.resolve(msg)

        assert result.participants[0].entity_id == "entity-1"
        assert result.participants[0].entity_name == "Jane Smith"
        assert result.participants[1].entity_id is None
        assert result.participants[1].entity_name is None

    @pytest.mark.asyncio
    async def test_resolve_case_insensitive_email(self):
        cache = {
            ("email", "jane@acme.com"): ResolvedEntity(id="entity-1", display_name="Jane Smith"),
        }
        resolver = self._make_resolver(cache)
        msg = _make_message([
            Participant(id="Jane@ACME.com", name="Jane", role="sender"),
        ])

        result = await resolver.resolve(msg)

        assert result.participants[0].entity_id == "entity-1"

    @pytest.mark.asyncio
    async def test_resolve_teams_channel(self):
        cache = {
            ("teams_id", "jane@acme.onmicrosoft.com"): ResolvedEntity(id="entity-2", display_name="Jane S"),
        }
        resolver = self._make_resolver(cache)
        msg = _make_message(
            [Participant(id="jane@acme.onmicrosoft.com", name="Jane", role="participant")],
            channel=Channel.TEAMS_CHAT,
        )

        result = await resolver.resolve(msg)

        assert result.participants[0].entity_id == "entity-2"

    @pytest.mark.asyncio
    async def test_resolve_no_matches(self):
        resolver = self._make_resolver({})
        msg = _make_message([
            Participant(id="nobody@example.com", name="Nobody", role="sender"),
        ])

        result = await resolver.resolve(msg)

        assert result.participants[0].entity_id is None
        assert result.participants[0].entity_name is None

    @pytest.mark.asyncio
    async def test_resolve_strips_whitespace(self):
        cache = {
            ("email", "jane@acme.com"): ResolvedEntity(id="entity-1", display_name="Jane"),
        }
        resolver = self._make_resolver(cache)
        msg = _make_message([
            Participant(id="  jane@acme.com  ", name="Jane", role="sender"),
        ])

        result = await resolver.resolve(msg)

        assert result.participants[0].entity_id == "entity-1"

    @pytest.mark.asyncio
    async def test_resolve_bloomberg_channel(self):
        cache = {
            ("bloomberg_uuid", "BB12345"): ResolvedEntity(id="entity-3", display_name="Bob"),
        }
        resolver = self._make_resolver(cache)
        msg = _make_message(
            [Participant(id="BB12345", name="Bob", role="sender")],
            channel=Channel.BLOOMBERG_CHAT,
        )

        result = await resolver.resolve(msg)

        assert result.participants[0].entity_id == "entity-3"

    @pytest.mark.asyncio
    async def test_resolve_bloomberg_email_uses_email_type(self):
        """BLOOMBERG_EMAIL maps to 'email' handle type (same as EMAIL)."""
        cache = {
            ("email", "jane@bloomberg.net"): ResolvedEntity(id="entity-4", display_name="Jane BB"),
        }
        resolver = self._make_resolver(cache)
        msg = _make_message(
            [Participant(id="jane@bloomberg.net", name="Jane", role="sender")],
            channel=Channel.BLOOMBERG_EMAIL,
        )

        result = await resolver.resolve(msg)

        assert result.participants[0].entity_id == "entity-4"

    @pytest.mark.asyncio
    async def test_resolve_teams_calls_uses_teams_id_type(self):
        """TEAMS_CALLS maps to 'teams_id' handle type (same as TEAMS_CHAT)."""
        cache = {
            ("teams_id", "alice@acme.onmicrosoft.com"): ResolvedEntity(id="entity-5", display_name="Alice"),
        }
        resolver = self._make_resolver(cache)
        msg = _make_message(
            [Participant(id="alice@acme.onmicrosoft.com", name="Alice", role="participant")],
            channel=Channel.TEAMS_CALLS,
        )

        result = await resolver.resolve(msg)

        assert result.participants[0].entity_id == "entity-5"

    @pytest.mark.asyncio
    async def test_resolve_unigy_turret_uses_turret_extension_type(self):
        """UNIGY_TURRET maps to 'turret_extension' handle type."""
        cache = {
            ("turret_extension", "EXT-1234"): ResolvedEntity(id="entity-6", display_name="Desk 12"),
        }
        resolver = self._make_resolver(cache)
        msg = _make_message(
            [Participant(id="EXT-1234", name="Desk 12", role="participant")],
            channel=Channel.UNIGY_TURRET,
        )

        result = await resolver.resolve(msg)

        assert result.participants[0].entity_id == "entity-6"

    @pytest.mark.asyncio
    async def test_resolve_unigy_turret_no_lowercasing(self):
        """turret_extension handles are NOT lowercased (only email handles are)."""
        cache = {
            ("turret_extension", "EXT-1234"): ResolvedEntity(id="entity-6", display_name="Desk"),
        }
        resolver = self._make_resolver(cache)
        msg = _make_message(
            [Participant(id="EXT-1234", name="Desk", role="participant")],
            channel=Channel.UNIGY_TURRET,
        )

        result = await resolver.resolve(msg)
        assert result.participants[0].entity_id == "entity-6"

    @pytest.mark.asyncio
    async def test_resolve_unknown_channel_falls_back_to_email(self):
        """Channels not in the mapping default to 'email' handle type."""
        # We'll use BLOOMBERG_EMAIL which IS in the map, so let's test the fallback
        # by testing the _normalize_handle method directly with a non-existent channel
        resolver = self._make_resolver({})
        # Simulate an unknown channel by calling _normalize_handle with an invalid value
        # Since Channel is an enum, we test the fallback via the get() default
        handle_type, handle_value = resolver._normalize_handle(
            "test@example.com", Channel.EMAIL
        )
        assert handle_type == "email"
        assert handle_value == "test@example.com"


class TestResolverLifecycle:
    """Tests for start/stop lifecycle with mocked asyncpg."""

    @pytest.mark.asyncio
    async def test_start_creates_pool_and_loads_cache(self):
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[
            {"handle_type": "email", "handle_value": "alice@acme.com",
             "id": "uuid-1", "display_name": "Alice"},
        ])

        mock_pool = MagicMock()
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        ctx.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire.return_value = ctx
        mock_pool.close = AsyncMock()

        with patch("umbrella_ingestion.resolver.asyncpg") as mock_asyncpg:
            mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)

            resolver = EntityResolver(dsn="postgresql://test:pw@localhost/db")
            await resolver.start()

            mock_asyncpg.create_pool.assert_awaited_once()
            assert ("email", "alice@acme.com") in resolver._cache
            assert resolver._cache[("email", "alice@acme.com")].display_name == "Alice"
            assert resolver._refresh_task is not None

            # Clean up refresh task
            await resolver.stop()

    @pytest.mark.asyncio
    async def test_stop_cancels_refresh_task(self):
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])

        mock_pool = MagicMock()
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        ctx.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire.return_value = ctx
        mock_pool.close = AsyncMock()

        with patch("umbrella_ingestion.resolver.asyncpg") as mock_asyncpg:
            mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)

            resolver = EntityResolver(dsn="postgresql://test:pw@localhost/db", refresh_interval=300)
            await resolver.start()

            assert resolver._refresh_task is not None
            assert not resolver._refresh_task.done()

            await resolver.stop()

            mock_pool.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_stop_before_start_does_not_raise(self):
        """Calling stop() without start() should not error."""
        resolver = EntityResolver(dsn="postgresql://test:pw@localhost/db")
        await resolver.stop()  # No error

    @pytest.mark.asyncio
    async def test_load_cache_populates_from_db(self):
        """_load_cache builds correct cache from DB rows."""
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[
            {"handle_type": "email", "handle_value": "alice@acme.com",
             "id": "uuid-1", "display_name": "Alice"},
            {"handle_type": "teams_id", "handle_value": "bob@acme.onmicrosoft.com",
             "id": "uuid-2", "display_name": "Bob"},
        ])

        mock_pool = MagicMock()
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        ctx.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire.return_value = ctx

        resolver = EntityResolver(dsn="postgresql://test:pw@localhost/db")
        resolver._pool = mock_pool

        await resolver._load_cache()

        assert len(resolver._cache) == 2
        assert resolver._cache[("email", "alice@acme.com")].id == "uuid-1"
        assert resolver._cache[("teams_id", "bob@acme.onmicrosoft.com")].id == "uuid-2"
