"""Tests for the tool catalog: es_search and sql_query."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

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
    body = call_kwargs.kwargs.get("body") or call_kwargs[1]["body"]
    filters = body["query"]["bool"]["filter"]
    assert any("term" in f for f in filters)
    assert any("range" in f for f in filters)


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
    session_mock = AsyncMock()

    async def _execute(stmt):
        result = MagicMock()
        result.keys.return_value = ["id", "name"]
        result.fetchall.return_value = [("uuid1", "Alice"), ("uuid2", "Bob")]
        return result

    session_mock.execute = _execute

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
