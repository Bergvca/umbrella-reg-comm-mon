"""Tests for the agent executor."""

from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_litellm import ChatLiteLLM
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from umbrella_agents.executor import _build_scope, execute_agent, execute_agent_streaming


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_agent_config():
    """Build a mock Agent ORM object."""
    model = MagicMock()
    model.provider = "openai"
    model.model_id = "gpt-4o"
    model.base_url = None
    model.max_tokens = 4096

    tool_obj = MagicMock()
    tool_obj.name = "es_search"

    agent_tool = MagicMock()
    agent_tool.tool = tool_obj
    agent_tool.tool_config = {}

    ds = MagicMock()
    ds.source_type = "elasticsearch"
    ds.source_identifier = "messages-*"

    agent = MagicMock()
    agent.id = uuid.uuid4()
    agent.name = "Test Agent"
    agent.system_prompt = "You are a test agent."
    agent.temperature = Decimal("0.00")
    agent.max_iterations = 5
    agent.model = model
    agent.tools = [agent_tool]
    agent.data_sources = [ds]
    agent.is_active = True

    return agent


def _make_session_and_factory(run_id: uuid.UUID, agent_config):
    """Return (session_mock, session_factory) wired up for execute_agent."""
    session = AsyncMock()
    run_obj = MagicMock()
    run_obj.id = run_id

    call_count = 0

    async def _execute(stmt, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        result.scalar_one_or_none.return_value = agent_config if call_count == 1 else run_obj
        result.scalar_one.return_value = run_obj
        return result

    session.execute = _execute
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock(side_effect=lambda obj, **kw: setattr(obj, "id", run_id))

    @asynccontextmanager
    async def session_factory():
        yield session

    return session, session_factory


# ---------------------------------------------------------------------------
# _build_scope
# ---------------------------------------------------------------------------


def test_build_scope():
    ds1 = MagicMock()
    ds1.source_type = "elasticsearch"
    ds1.source_identifier = "messages-*"

    ds2 = MagicMock()
    ds2.source_type = "postgresql"
    ds2.source_identifier = "entity"

    scope = _build_scope([ds1, ds2])
    assert scope.allowed_es_indices == ["messages-*"]
    assert scope.allowed_pg_schemas == ["entity"]


def test_build_scope_empty():
    scope = _build_scope([])
    assert scope.allowed_es_indices == []
    assert scope.allowed_pg_schemas == []


# ---------------------------------------------------------------------------
# ChatLiteLLM integration sanity check
# ---------------------------------------------------------------------------


def test_chat_litellm_is_langchain_runnable():
    """ChatLiteLLM must be a LangChain Runnable so create_react_agent accepts it."""
    from langchain_core.runnables import Runnable

    llm = ChatLiteLLM(model="openai/gpt-4o")
    assert isinstance(llm, Runnable)


# ---------------------------------------------------------------------------
# execute_agent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_agent_success():
    """Test full execution flow with mocked dependencies."""
    agent_id = uuid.uuid4()
    user_id = uuid.uuid4()
    run_id = uuid.uuid4()

    agent_config = _make_agent_config()
    _, session_factory = _make_session_and_factory(run_id, agent_config)
    es_client = AsyncMock()

    mock_result = {"messages": [AIMessage(content="Here are the results")]}

    with (
        patch("umbrella_agents.executor.load_agent_config", new_callable=AsyncMock, return_value=agent_config),
        patch("umbrella_agents.executor.create_react_agent") as mock_create,
    ):
        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock(return_value=mock_result)
        mock_create.return_value = mock_graph

        result = await execute_agent(
            agent_id=agent_id,
            user_input="Find me some emails",
            triggered_by=user_id,
            session_factory=session_factory,
            es_client=es_client,
        )

    assert result["status"] == "completed"
    assert result["output"]["response"] == "Here are the results"
    assert result["run_id"] is not None


@pytest.mark.asyncio
async def test_execute_agent_failure():
    """Test that exceptions are caught and the run is marked as failed."""
    agent_id = uuid.uuid4()
    user_id = uuid.uuid4()
    run_id = uuid.uuid4()

    agent_config = _make_agent_config()
    _, session_factory = _make_session_and_factory(run_id, agent_config)
    es_client = AsyncMock()

    with (
        patch("umbrella_agents.executor.load_agent_config", new_callable=AsyncMock, return_value=agent_config),
        patch("umbrella_agents.executor.create_react_agent") as mock_create,
    ):
        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock(side_effect=RuntimeError("LLM exploded"))
        mock_create.return_value = mock_graph

        result = await execute_agent(
            agent_id=agent_id,
            user_input="Fail please",
            triggered_by=user_id,
            session_factory=session_factory,
            es_client=es_client,
        )

    assert result["status"] == "failed"
    assert "LLM exploded" in result["error_message"]


@pytest.mark.asyncio
async def test_execute_agent_empty_messages():
    """When the graph returns no messages, output should be an empty response."""
    agent_id = uuid.uuid4()
    user_id = uuid.uuid4()
    run_id = uuid.uuid4()

    agent_config = _make_agent_config()
    _, session_factory = _make_session_and_factory(run_id, agent_config)
    es_client = AsyncMock()

    with (
        patch("umbrella_agents.executor.load_agent_config", new_callable=AsyncMock, return_value=agent_config),
        patch("umbrella_agents.executor.create_react_agent") as mock_create,
    ):
        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock(return_value={"messages": []})
        mock_create.return_value = mock_graph

        result = await execute_agent(
            agent_id=agent_id,
            user_input="Hello",
            triggered_by=user_id,
            session_factory=session_factory,
            es_client=es_client,
        )

    assert result["status"] == "completed"
    assert result["output"] == {"response": ""}


# ---------------------------------------------------------------------------
# execute_agent_streaming
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_agent_streaming_success():
    """Streaming executor should push events and end with run_completed + sentinel."""
    agent_id = uuid.uuid4()
    user_id = uuid.uuid4()
    run_id = uuid.uuid4()

    agent_config = _make_agent_config()
    _, session_factory = _make_session_and_factory(run_id, agent_config)
    es_client = AsyncMock()
    queue: asyncio.Queue = asyncio.Queue()
    cancelled = asyncio.Event()

    mock_result = {"messages": [AIMessage(content="Streamed answer")]}

    with (
        patch("umbrella_agents.executor.load_agent_config", new_callable=AsyncMock, return_value=agent_config),
        patch("umbrella_agents.executor.create_react_agent") as mock_create,
    ):
        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock(return_value=mock_result)
        mock_create.return_value = mock_graph

        await execute_agent_streaming(
            agent_id=agent_id,
            user_input="Stream this",
            triggered_by=user_id,
            run_id=run_id,
            session_factory=session_factory,
            es_client=es_client,
            event_queue=queue,
            cancelled=cancelled,
        )

    # Drain events
    events = []
    while not queue.empty():
        events.append(queue.get_nowait())

    # Must have run_started, run_completed, and a None sentinel
    event_types = [e["event"] for e in events if e is not None]
    assert "run_started" in event_types
    assert "run_completed" in event_types
    assert events[-1] is None  # sentinel


@pytest.mark.asyncio
async def test_execute_agent_streaming_failure():
    """When the graph raises, streaming executor should push run_failed."""
    agent_id = uuid.uuid4()
    user_id = uuid.uuid4()
    run_id = uuid.uuid4()

    agent_config = _make_agent_config()
    _, session_factory = _make_session_and_factory(run_id, agent_config)
    es_client = AsyncMock()
    queue: asyncio.Queue = asyncio.Queue()
    cancelled = asyncio.Event()

    with (
        patch("umbrella_agents.executor.load_agent_config", new_callable=AsyncMock, return_value=agent_config),
        patch("umbrella_agents.executor.create_react_agent") as mock_create,
    ):
        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock(side_effect=RuntimeError("Boom"))
        mock_create.return_value = mock_graph

        await execute_agent_streaming(
            agent_id=agent_id,
            user_input="Fail stream",
            triggered_by=user_id,
            run_id=run_id,
            session_factory=session_factory,
            es_client=es_client,
            event_queue=queue,
            cancelled=cancelled,
        )

    events = []
    while not queue.empty():
        events.append(queue.get_nowait())

    event_types = [e["event"] for e in events if e is not None]
    assert "run_failed" in event_types
    failed_event = next(e for e in events if e and e["event"] == "run_failed")
    assert "Boom" in failed_event["data"]["error_message"]
    assert events[-1] is None


@pytest.mark.asyncio
async def test_execute_agent_streaming_cancelled():
    """Pre-cancelled event should result in run_cancelled."""
    agent_id = uuid.uuid4()
    user_id = uuid.uuid4()
    run_id = uuid.uuid4()

    agent_config = _make_agent_config()
    _, session_factory = _make_session_and_factory(run_id, agent_config)
    es_client = AsyncMock()
    queue: asyncio.Queue = asyncio.Queue()
    cancelled = asyncio.Event()
    cancelled.set()  # pre-cancel

    with (
        patch("umbrella_agents.executor.load_agent_config", new_callable=AsyncMock, return_value=agent_config),
        patch("umbrella_agents.executor.create_react_agent") as mock_create,
    ):
        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock(return_value={"messages": []})
        mock_create.return_value = mock_graph

        await execute_agent_streaming(
            agent_id=agent_id,
            user_input="Cancel me",
            triggered_by=user_id,
            run_id=run_id,
            session_factory=session_factory,
            es_client=es_client,
            event_queue=queue,
            cancelled=cancelled,
        )

    events = []
    while not queue.empty():
        events.append(queue.get_nowait())

    event_types = [e["event"] for e in events if e is not None]
    assert "run_cancelled" in event_types
    assert events[-1] is None
