"""Tests for the AlertPercolator — ES percolation + PG alert insertion."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from umbrella_ingestion.config import AlertDBConfig, ElasticsearchConfig
from umbrella_ingestion.percolator import AlertPercolator


def _make_percolator(
    es_mock=None,
    pool_mock=None,
    *,
    es_url: str = "http://localhost:9200",
    percolator_index: str = "umbrella-alert-rules",
    alert_dsn: str = "postgresql://alert_rw:pw@localhost/db",
) -> AlertPercolator:
    es_config = ElasticsearchConfig(url=es_url, percolator_index=percolator_index)
    alert_config = AlertDBConfig(dsn=alert_dsn)
    perc = AlertPercolator(es_config=es_config, alert_db_config=alert_config)
    if es_mock is not None:
        perc._es = es_mock
    if pool_mock is not None:
        perc._pool = pool_mock
    return perc


def _make_pool_mock(execute_return="INSERT 0 1"):
    """Build a mock asyncpg pool that returns a given status from execute."""
    conn_mock = AsyncMock()
    conn_mock.execute = AsyncMock(return_value=execute_return)

    pool_mock = MagicMock()
    # asyncpg pool.acquire() is used as `async with pool.acquire() as conn:`
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=conn_mock)
    ctx.__aexit__ = AsyncMock(return_value=False)
    pool_mock.acquire.return_value = ctx
    pool_mock.close = AsyncMock()

    return pool_mock, conn_mock


def _make_es_hits(*hits):
    """Build an ES search response body with the given hits."""
    return {"hits": {"hits": list(hits)}}


def _make_hit(rule_id=None, rule_name="Test Rule", severity="high"):
    """Build a single ES hit _source for a percolator match."""
    src = {"rule_name": rule_name, "severity": severity}
    if rule_id is not None:
        src["rule_id"] = str(rule_id) if not isinstance(rule_id, str) else rule_id
    return {"_id": "hit-1", "_source": src}


# ── Early returns ────────────────────────────────────────────────


class TestPercolateGuards:
    @pytest.mark.asyncio
    async def test_returns_zero_when_no_es(self):
        perc = _make_percolator()
        perc._es = None
        perc._pool = MagicMock()
        result = await perc.percolate("msg-1", "messages-2025.06", {}, None)
        assert result == 0

    @pytest.mark.asyncio
    async def test_returns_zero_when_no_pool(self):
        perc = _make_percolator()
        perc._es = AsyncMock()
        perc._pool = None
        result = await perc.percolate("msg-1", "messages-2025.06", {}, None)
        assert result == 0


# ── Happy path ───────────────────────────────────────────────────


class TestPercolateHappyPath:
    @pytest.mark.asyncio
    async def test_single_hit_creates_alert(self):
        rule_id = uuid.uuid4()
        es_mock = AsyncMock()
        es_mock.search = AsyncMock(return_value=_make_es_hits(
            _make_hit(rule_id=rule_id, rule_name="Insider Trading", severity="high"),
        ))

        pool_mock, conn_mock = _make_pool_mock("INSERT 0 1")
        perc = _make_percolator(es_mock=es_mock, pool_mock=pool_mock)

        ts = datetime(2025, 6, 1, 12, 0, tzinfo=timezone.utc)
        doc = {"body_text": "suspicious activity", "channel": "email"}

        created = await perc.percolate("msg-1", "messages-2025.06", doc, ts)

        assert created == 1
        conn_mock.execute.assert_awaited_once()
        call_args = conn_mock.execute.call_args[0]
        assert call_args[1] == "Insider Trading"  # rule_name
        assert call_args[2] == rule_id              # rule_id UUID
        assert call_args[3] == "messages-2025.06"   # es_index
        assert call_args[4] == "msg-1"              # message_id
        assert call_args[5] == ts                   # timestamp
        assert call_args[6] == "high"               # severity

    @pytest.mark.asyncio
    async def test_multiple_hits_counts_correctly(self):
        rule1 = uuid.uuid4()
        rule2 = uuid.uuid4()
        es_mock = AsyncMock()
        es_mock.search = AsyncMock(return_value=_make_es_hits(
            _make_hit(rule_id=rule1, rule_name="Rule A"),
            _make_hit(rule_id=rule2, rule_name="Rule B"),
        ))

        pool_mock, conn_mock = _make_pool_mock("INSERT 0 1")
        perc = _make_percolator(es_mock=es_mock, pool_mock=pool_mock)

        ts = datetime(2025, 6, 1, 12, 0, tzinfo=timezone.utc)
        created = await perc.percolate("msg-1", "messages-2025.06", {}, ts)

        assert created == 2
        assert conn_mock.execute.await_count == 2

    @pytest.mark.asyncio
    async def test_duplicate_insert_returns_zero_created(self):
        """ON CONFLICT DO NOTHING → 'INSERT 0 0' → not counted."""
        es_mock = AsyncMock()
        es_mock.search = AsyncMock(return_value=_make_es_hits(
            _make_hit(rule_id=uuid.uuid4()),
        ))

        pool_mock, conn_mock = _make_pool_mock("INSERT 0 0")
        perc = _make_percolator(es_mock=es_mock, pool_mock=pool_mock)

        created = await perc.percolate("msg-1", "messages-2025.06", {}, None)
        assert created == 0


# ── No hits ──────────────────────────────────────────────────────


class TestPercolateNoHits:
    @pytest.mark.asyncio
    async def test_no_matching_rules_returns_zero(self):
        es_mock = AsyncMock()
        es_mock.search = AsyncMock(return_value=_make_es_hits())

        pool_mock, _ = _make_pool_mock()
        perc = _make_percolator(es_mock=es_mock, pool_mock=pool_mock)

        created = await perc.percolate("msg-1", "messages-2025.06", {}, None)
        assert created == 0


# ── Error handling ───────────────────────────────────────────────


class TestPercolateErrors:
    @pytest.mark.asyncio
    async def test_es_exception_returns_zero(self):
        """Fail-open: ES error → log + return 0."""
        es_mock = AsyncMock()
        es_mock.search = AsyncMock(side_effect=Exception("ES connection refused"))

        pool_mock, _ = _make_pool_mock()
        perc = _make_percolator(es_mock=es_mock, pool_mock=pool_mock)

        created = await perc.percolate("msg-1", "messages-2025.06", {}, None)
        assert created == 0

    @pytest.mark.asyncio
    async def test_invalid_uuid_rule_id_skipped(self):
        """rule_id that isn't a valid UUID is silently skipped."""
        es_mock = AsyncMock()
        es_mock.search = AsyncMock(return_value=_make_es_hits(
            _make_hit(rule_id="not-a-uuid"),
        ))

        pool_mock, conn_mock = _make_pool_mock()
        perc = _make_percolator(es_mock=es_mock, pool_mock=pool_mock)

        created = await perc.percolate("msg-1", "messages-2025.06", {}, None)
        assert created == 0
        conn_mock.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_missing_rule_id_skipped(self):
        """Hit with no rule_id field is silently skipped."""
        es_mock = AsyncMock()
        es_mock.search = AsyncMock(return_value=_make_es_hits(
            _make_hit(rule_id=None),  # No rule_id in _source
        ))

        pool_mock, conn_mock = _make_pool_mock()
        perc = _make_percolator(es_mock=es_mock, pool_mock=pool_mock)

        created = await perc.percolate("msg-1", "messages-2025.06", {}, None)
        assert created == 0
        conn_mock.execute.assert_not_awaited()


# ── Timestamp handling ───────────────────────────────────────────


class TestPercolateTimestamp:
    @pytest.mark.asyncio
    async def test_naive_datetime_gets_utc(self):
        """Naive datetime (no tzinfo) should get UTC attached."""
        rule_id = uuid.uuid4()
        es_mock = AsyncMock()
        es_mock.search = AsyncMock(return_value=_make_es_hits(
            _make_hit(rule_id=rule_id),
        ))

        pool_mock, conn_mock = _make_pool_mock("INSERT 0 1")
        perc = _make_percolator(es_mock=es_mock, pool_mock=pool_mock)

        naive_ts = datetime(2025, 6, 1, 12, 0, 0)  # no tzinfo
        await perc.percolate("msg-1", "messages-2025.06", {}, naive_ts)

        call_args = conn_mock.execute.call_args[0]
        ts_passed = call_args[5]
        assert ts_passed.tzinfo == timezone.utc
        assert ts_passed.year == 2025

    @pytest.mark.asyncio
    async def test_none_timestamp_passed_through(self):
        """None timestamp is passed to Postgres as-is."""
        rule_id = uuid.uuid4()
        es_mock = AsyncMock()
        es_mock.search = AsyncMock(return_value=_make_es_hits(
            _make_hit(rule_id=rule_id),
        ))

        pool_mock, conn_mock = _make_pool_mock("INSERT 0 1")
        perc = _make_percolator(es_mock=es_mock, pool_mock=pool_mock)

        await perc.percolate("msg-1", "messages-2025.06", {}, None)

        call_args = conn_mock.execute.call_args[0]
        assert call_args[5] is None

    @pytest.mark.asyncio
    async def test_aware_datetime_unchanged(self):
        """Timezone-aware datetime is passed through without modification."""
        rule_id = uuid.uuid4()
        es_mock = AsyncMock()
        es_mock.search = AsyncMock(return_value=_make_es_hits(
            _make_hit(rule_id=rule_id),
        ))

        pool_mock, conn_mock = _make_pool_mock("INSERT 0 1")
        perc = _make_percolator(es_mock=es_mock, pool_mock=pool_mock)

        aware_ts = datetime(2025, 6, 1, 12, 0, tzinfo=timezone.utc)
        await perc.percolate("msg-1", "messages-2025.06", {}, aware_ts)

        call_args = conn_mock.execute.call_args[0]
        assert call_args[5] is aware_ts


# ── Lifecycle ────────────────────────────────────────────────────


class TestPercolatorLifecycle:
    @pytest.mark.asyncio
    async def test_start_creates_es_and_pool(self):
        with patch("umbrella_ingestion.percolator.AsyncElasticsearch") as MockES, \
             patch("umbrella_ingestion.percolator.asyncpg") as mock_asyncpg:
            mock_es_instance = AsyncMock()
            MockES.return_value = mock_es_instance

            mock_pool = AsyncMock()
            mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)

            perc = _make_percolator()
            await perc.start()

            MockES.assert_called_once()
            mock_asyncpg.create_pool.assert_awaited_once()
            assert perc._es is mock_es_instance
            assert perc._pool is mock_pool

    @pytest.mark.asyncio
    async def test_start_without_dsn_skips_pool(self):
        with patch("umbrella_ingestion.percolator.AsyncElasticsearch") as MockES, \
             patch("umbrella_ingestion.percolator.asyncpg") as mock_asyncpg:
            MockES.return_value = AsyncMock()
            mock_asyncpg.create_pool = AsyncMock()

            es_config = ElasticsearchConfig()
            alert_config = AlertDBConfig(dsn=None)
            perc = AlertPercolator(es_config=es_config, alert_db_config=alert_config)
            await perc.start()

            mock_asyncpg.create_pool.assert_not_awaited()
            assert perc._pool is None

    @pytest.mark.asyncio
    async def test_stop_closes_es_and_pool(self):
        es_mock = AsyncMock()
        es_mock.close = AsyncMock()
        pool_mock = MagicMock()
        pool_mock.close = AsyncMock()

        perc = _make_percolator(es_mock=es_mock, pool_mock=pool_mock)
        await perc.stop()

        es_mock.close.assert_awaited_once()
        pool_mock.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_stop_when_not_started(self):
        """stop() before start() should not raise."""
        perc = _make_percolator()
        await perc.stop()  # No error


# ── ES query shape ───────────────────────────────────────────────


class TestPercolateQueryShape:
    @pytest.mark.asyncio
    async def test_percolate_query_uses_correct_index_and_document(self):
        es_mock = AsyncMock()
        es_mock.search = AsyncMock(return_value=_make_es_hits())

        pool_mock, _ = _make_pool_mock()
        perc = _make_percolator(
            es_mock=es_mock,
            pool_mock=pool_mock,
        )

        doc = {"body_text": "test content", "channel": "email"}
        await perc.percolate("msg-1", "messages-2025.06", doc, None)

        call_kwargs = es_mock.search.call_args.kwargs
        assert call_kwargs["index"] == "umbrella-alert-rules"
        body = call_kwargs["body"]
        assert body["query"]["percolate"]["field"] == "query"
        assert body["query"]["percolate"]["document"] == doc

    @pytest.mark.asyncio
    async def test_defaults_severity_and_rule_name(self):
        """Hits missing severity/rule_name get defaults ('medium' / '')."""
        rule_id = uuid.uuid4()
        es_mock = AsyncMock()
        es_mock.search = AsyncMock(return_value=_make_es_hits(
            {"_id": "h1", "_source": {"rule_id": str(rule_id)}},
        ))

        pool_mock, conn_mock = _make_pool_mock("INSERT 0 1")
        perc = _make_percolator(es_mock=es_mock, pool_mock=pool_mock)

        await perc.percolate("msg-1", "messages-2025.06", {}, None)

        call_args = conn_mock.execute.call_args[0]
        assert call_args[1] == ""        # rule_name default
        assert call_args[6] == "medium"  # severity default
