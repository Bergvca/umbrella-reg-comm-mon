"""Tests for the tool catalog: es_search, sql_query, alert_lookup."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest

from umbrella_agents.tools.alert_lookup import AlertLookupTool
from umbrella_agents.tools.es_search import ESSearchTool
from umbrella_agents.tools.registry import DataSourceScope, ToolRegistry
from umbrella_agents.tools.sql_query import SQLQueryTool


def _make_scope(**kwargs):
    return DataSourceScope(
        allowed_es_indices=kwargs.get("es", ["messages-*"]),
        allowed_pg_schemas=kwargs.get("pg", ["entity", "alert"]),
    )


def _make_es_tool(scope=None, es_client=None):
    return ESSearchTool(
        scope=scope or _make_scope(),
        es_client=es_client or AsyncMock(),
        session_factory=AsyncMock(),
        tool_config={},
    )


def _make_sql_tool(scope=None, session_factory=None):
    return SQLQueryTool(
        scope=scope or _make_scope(),
        es_client=None,
        session_factory=session_factory or AsyncMock(),
        tool_config={},
    )


# ── ESSearchTool ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_es_search_returns_results():
    es_mock = AsyncMock()
    es_mock.search = AsyncMock(return_value={
        "hits": {
            "total": {"value": 2},
            "hits": [
                {
                    "_id": "doc1",
                    "_index": "messages-2024",
                    "_score": 1.5,
                    "_source": {"body_text": "quarterly earnings report", "channel": "email"},
                    "highlight": {"body_text": ["<em>quarterly</em> earnings"]},
                },
                {
                    "_id": "doc2",
                    "_index": "messages-2024",
                    "_score": 1.0,
                    "_source": {"body_text": "Q3 earnings call", "channel": "email"},
                    "highlight": {},
                },
            ],
        }
    })

    tool = _make_es_tool(es_client=es_mock)
    result = json.loads(await tool._arun(query="quarterly earnings"))
    assert result["total"] == 2
    assert len(result["results"]) == 2
    assert result["results"][0]["id"] == "doc1"


@pytest.mark.asyncio
async def test_es_search_rejects_unauthorized_index():
    tool = _make_es_tool(scope=_make_scope(es=["messages-*"]))
    result = json.loads(await tool._arun(query="test", index="secret-index"))
    assert "error" in result
    assert "Access denied" in result["error"]


@pytest.mark.asyncio
async def test_es_search_allows_matching_index():
    es_mock = AsyncMock()
    es_mock.search = AsyncMock(return_value={"hits": {"total": {"value": 0}, "hits": []}})
    tool = _make_es_tool(scope=_make_scope(es=["messages-*"]), es_client=es_mock)

    result = json.loads(await tool._arun(query="test", index="messages-*"))
    assert result["total"] == 0
    es_mock.search.assert_called_once()


@pytest.mark.asyncio
async def test_es_search_with_filters():
    es_mock = AsyncMock()
    es_mock.search = AsyncMock(return_value={"hits": {"total": {"value": 0}, "hits": []}})
    tool = _make_es_tool(es_client=es_mock)

    await tool._arun(query="test", filters={"channel": "email", "timestamp": {"gte": "now-1w"}})
    call_kwargs = es_mock.search.call_args
    query_dsl = call_kwargs.kwargs.get("query")
    filters = query_dsl["bool"]["filter"]
    assert any("term" in f for f in filters)
    assert any("range" in f for f in filters)


@pytest.mark.asyncio
async def test_es_search_with_field_selection():
    """When fields are specified, only those fields should be in _source."""
    es_mock = AsyncMock()
    es_mock.search = AsyncMock(return_value={
        "hits": {
            "total": {"value": 1},
            "hits": [{
                "_id": "doc1", "_index": "messages-2024", "_score": 1.0,
                "_source": {"channel": "email", "timestamp": "2024-01-01"},
            }],
        }
    })
    tool = _make_es_tool(es_client=es_mock)

    result = json.loads(await tool._arun(
        query="test", fields=["channel", "timestamp"],
    ))
    assert result["total"] == 1
    # Verify _source filtering was requested
    call_kwargs = es_mock.search.call_args.kwargs
    assert call_kwargs["source"] == ["channel", "timestamp"]


@pytest.mark.asyncio
async def test_es_search_aggregation_only():
    """With aggs and size=0, return aggregation results without documents."""
    es_mock = AsyncMock()
    es_mock.search = AsyncMock(return_value={
        "hits": {"total": {"value": 42}, "hits": []},
        "aggregations": {
            "by_channel": {
                "buckets": [
                    {"key": "email", "doc_count": 30},
                    {"key": "chat", "doc_count": 12},
                ],
            },
        },
    })
    tool = _make_es_tool(es_client=es_mock)

    result = json.loads(await tool._arun(
        query="*",
        aggs={"by_channel": {"terms": {"field": "channel", "size": 10}}},
        size=0,
    ))
    assert result["total"] == 42
    assert "results" not in result  # size=0 → no docs
    assert result["aggregations"]["by_channel"]["buckets"][0]["key"] == "email"
    assert result["aggregations"]["by_channel"]["buckets"][0]["doc_count"] == 30


@pytest.mark.asyncio
async def test_es_search_match_all():
    """Query '*' should use match_all instead of multi_match."""
    es_mock = AsyncMock()
    es_mock.search = AsyncMock(return_value={"hits": {"total": {"value": 0}, "hits": []}})
    tool = _make_es_tool(es_client=es_mock)

    await tool._arun(query="*", size=0)
    call_kwargs = es_mock.search.call_args.kwargs
    assert call_kwargs["query"] == {"match_all": {}}
    # match_all + size=0 should not include highlights
    assert "highlight" not in call_kwargs


# ── SQLQueryTool ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sql_query_rejects_write():
    tool = _make_sql_tool()
    result = json.loads(await tool._arun(query="INSERT INTO foo VALUES (1)"))
    assert "error" in result
    assert "Only SELECT" in result["error"]


@pytest.mark.asyncio
async def test_sql_query_rejects_drop():
    tool = _make_sql_tool()
    result = json.loads(await tool._arun(query="DROP TABLE entity.entities"))
    assert "error" in result
    assert "only select" in result["error"].lower() or "forbidden" in result["error"].lower()


@pytest.mark.asyncio
async def test_sql_query_rejects_multi_statement():
    tool = _make_sql_tool()
    result = json.loads(await tool._arun(query="SELECT 1; DROP TABLE foo"))
    assert "error" in result
    # May be caught by write keyword check or multi-statement check
    assert "error" in result


@pytest.mark.asyncio
async def test_sql_query_allows_select():
    conn_mock = AsyncMock()

    async def _execute(stmt):
        result = MagicMock()
        result.keys.return_value = ["id", "name"]
        result.fetchall.return_value = [("uuid1", "Alice"), ("uuid2", "Bob")]
        return result

    conn_mock.execute = _execute

    session_mock = AsyncMock()
    session_mock.connection = AsyncMock(return_value=conn_mock)

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _session_factory():
        yield session_mock

    tool = _make_sql_tool(session_factory=_session_factory)
    result = json.loads(await tool._arun(query="SELECT id, name FROM entities LIMIT 10"))
    assert result["row_count"] == 2
    assert result["columns"] == ["id", "name"]
    assert result["rows"][0]["name"] == "Alice"


@pytest.mark.asyncio
async def test_sql_query_no_schemas_allowed():
    tool = _make_sql_tool(scope=DataSourceScope(allowed_es_indices=[], allowed_pg_schemas=[]))
    result = json.loads(await tool._arun(query="SELECT 1"))
    assert "error" in result
    assert "No PostgreSQL" in result["error"]


# ── ToolRegistry ─────────────────────────────────────────────────

def test_registry_builds_tools():
    registry = ToolRegistry()
    registry.register("es_search", ESSearchTool)
    registry.register("sql_query", SQLQueryTool)

    scope = _make_scope()
    es_mock = AsyncMock()
    session_factory = AsyncMock()

    tools = registry.build_tools(
        tool_names=["es_search", "sql_query"],
        scope=scope,
        es_client=es_mock,
        session_factory=session_factory,
    )
    assert len(tools) == 2
    names = {t.name for t in tools}
    assert names == {"es_search", "sql_query"}


def test_registry_ignores_unknown_tools():
    registry = ToolRegistry()
    tools = registry.build_tools(
        tool_names=["nonexistent"],
        scope=_make_scope(),
        es_client=AsyncMock(),
        session_factory=AsyncMock(),
    )
    assert tools == []


# ── AlertLookupTool ─────────────────────────────────────────────


def _make_alert_session_factory(rows, columns=None):
    """Build a mock session_factory that returns the given rows from a query."""
    if columns is None:
        columns = ["id", "name", "severity", "status", "channel",
                    "es_index", "es_document_id", "created_at",
                    "rule_name", "policy_name"]

    conn_mock = AsyncMock()
    call_count = 0

    async def _execute(stmt, params=None):
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        # First call is SET TRANSACTION READ ONLY, second is the actual query
        if call_count <= 1:
            return result
        result.keys.return_value = columns
        result.fetchall.return_value = rows
        return result

    conn_mock.execute = _execute

    session_mock = AsyncMock()
    session_mock.connection = AsyncMock(return_value=conn_mock)

    @asynccontextmanager
    async def factory():
        yield session_mock

    return factory


def _make_alert_tool(session_factory=None, es_client=None, scope=None):
    return AlertLookupTool(
        scope=scope or _make_scope(),
        es_client=es_client,
        session_factory=session_factory or AsyncMock(),
        tool_config={},
    )


_SAMPLE_ALERT_ROW = (
    "alert-uuid-1", "Insider trading pattern", "high", "open", "email",
    "messages-2025.01", "doc-abc", "2025-01-15T10:00:00",
    "Suspicious keyword match", "Market Abuse Policy",
)


@pytest.mark.asyncio
async def test_alert_lookup_returns_alerts():
    factory = _make_alert_session_factory([_SAMPLE_ALERT_ROW])
    tool = _make_alert_tool(session_factory=factory)

    result = json.loads(await tool._arun(policy_name="Market Abuse", fetch_events=False))
    assert result["total"] == 1
    alert = result["alerts"][0]
    assert alert["alert_id"] == "alert-uuid-1"
    assert alert["policy_name"] == "Market Abuse Policy"
    assert alert["severity"] == "high"
    assert alert["link"] == "/messages/messages-2025.01/doc-abc"


@pytest.mark.asyncio
async def test_alert_lookup_no_results():
    factory = _make_alert_session_factory([])
    tool = _make_alert_tool(session_factory=factory)

    result = json.loads(await tool._arun(severity="critical", fetch_events=False))
    assert result["total"] == 0
    assert result["alerts"] == []


@pytest.mark.asyncio
async def test_alert_lookup_fetches_events():
    factory = _make_alert_session_factory([_SAMPLE_ALERT_ROW])

    es_mock = AsyncMock()
    es_mock.mget = AsyncMock(return_value={
        "docs": [{
            "_index": "messages-2025.01",
            "_id": "doc-abc",
            "found": True,
            "_source": {
                "body_text": "Buy 10k shares before announcement",
                "channel": "email",
                "timestamp": "2025-01-15T09:30:00Z",
            },
        }],
    })

    tool = _make_alert_tool(session_factory=factory, es_client=es_mock)
    result = json.loads(await tool._arun(fetch_events=True))

    assert result["total"] == 1
    alert = result["alerts"][0]
    assert "event" in alert
    assert alert["event"]["body_text"] == "Buy 10k shares before announcement"
    es_mock.mget.assert_called_once()


@pytest.mark.asyncio
async def test_alert_lookup_with_event_fields():
    factory = _make_alert_session_factory([_SAMPLE_ALERT_ROW])

    es_mock = AsyncMock()
    es_mock.mget = AsyncMock(return_value={
        "docs": [{
            "_index": "messages-2025.01",
            "_id": "doc-abc",
            "found": True,
            "_source": {"body_text": "content"},
        }],
    })

    tool = _make_alert_tool(session_factory=factory, es_client=es_mock)
    await tool._arun(fetch_events=True, event_fields=["body_text"])

    call_kwargs = es_mock.mget.call_args.kwargs
    assert call_kwargs["source_includes"] == ["body_text"]


@pytest.mark.asyncio
async def test_alert_lookup_continues_on_es_failure():
    """If ES fails, alerts should still be returned without events."""
    factory = _make_alert_session_factory([_SAMPLE_ALERT_ROW])

    es_mock = AsyncMock()
    es_mock.mget = AsyncMock(side_effect=Exception("ES down"))

    tool = _make_alert_tool(session_factory=factory, es_client=es_mock)
    result = json.loads(await tool._arun(fetch_events=True))

    assert result["total"] == 1
    assert "event" not in result["alerts"][0]


@pytest.mark.asyncio
async def test_alert_lookup_pg_failure():
    """If PG query fails, return error."""
    conn_mock = AsyncMock()
    conn_mock.execute = AsyncMock(side_effect=Exception("connection refused"))

    session_mock = AsyncMock()
    session_mock.connection = AsyncMock(return_value=conn_mock)

    @asynccontextmanager
    async def factory():
        yield session_mock

    tool = _make_alert_tool(session_factory=factory)
    result = json.loads(await tool._arun(fetch_events=False))
    assert "error" in result
