"""Tests for the agent executor."""

from __future__ import annotations

import json
import uuid
from contextlib import asynccontextmanager
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from umbrella_agents.executor import _build_scope, _LiteLLMChatModel, execute_agent


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


@pytest.mark.asyncio
async def test_litellm_chat_model_ainvoke():
    """Test the LiteLLM chat model wrapper."""
    from langchain_core.messages import HumanMessage, SystemMessage

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Hello from the model"
    mock_response.choices[0].message.tool_calls = None

    with patch("umbrella_agents.executor.acompletion", new_callable=AsyncMock, return_value=mock_response):
        model = _LiteLLMChatModel(model="openai/gpt-4o")
        result = await model.ainvoke([
            SystemMessage(content="You are helpful"),
            HumanMessage(content="Hi"),
        ])

    assert result.content == "Hello from the model"
    assert result.tool_calls == []


@pytest.mark.asyncio
async def test_litellm_chat_model_with_tool_calls():
    """Test tool calls are parsed correctly."""
    from langchain_core.messages import HumanMessage

    tc = MagicMock()
    tc.id = "call_123"
    tc.function.name = "es_search"
    tc.function.arguments = '{"query": "test"}'

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = ""
    mock_response.choices[0].message.tool_calls = [tc]

    with patch("umbrella_agents.executor.acompletion", new_callable=AsyncMock, return_value=mock_response):
        model = _LiteLLMChatModel(model="openai/gpt-4o")
        model_with_tools = model.bind_tools([])
        result = await model_with_tools.ainvoke([HumanMessage(content="search")])

    assert len(result.tool_calls) == 1
    assert result.tool_calls[0]["name"] == "es_search"
    assert result.tool_calls[0]["args"] == {"query": "test"}


@pytest.mark.asyncio
async def test_execute_agent_success():
    """Test full execution flow with mocked dependencies."""
    agent_id = uuid.uuid4()
    user_id = uuid.uuid4()
    run_id = uuid.uuid4()

    agent_config = _make_agent_config()

    # Mock session factory
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
    session.refresh = AsyncMock(side_effect=lambda obj, **kw: setattr(obj, 'id', run_id))

    @asynccontextmanager
    async def session_factory():
        yield session

    es_client = AsyncMock()

    # Mock the graph execution
    from langchain_core.messages import AIMessage
    mock_result = {"messages": [AIMessage(content="Here are the results")]}

    with patch("umbrella_agents.executor.load_agent_config", new_callable=AsyncMock, return_value=agent_config), \
         patch("umbrella_agents.executor.create_react_agent") as mock_create:
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
    session.refresh = AsyncMock(side_effect=lambda obj, **kw: setattr(obj, 'id', run_id))

    @asynccontextmanager
    async def session_factory():
        yield session

    es_client = AsyncMock()

    with patch("umbrella_agents.executor.load_agent_config", new_callable=AsyncMock, return_value=agent_config), \
         patch("umbrella_agents.executor.create_react_agent") as mock_create:
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
