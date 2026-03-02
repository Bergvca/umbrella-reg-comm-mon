"""Tests for the StreamingAuditCallback and streaming executor."""

from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from umbrella_agents.callbacks.streaming import StreamingAuditCallback
from umbrella_agents.executor import execute_agent_streaming


# ---------------------------------------------------------------------------
# StreamingAuditCallback tests
# ---------------------------------------------------------------------------


@pytest.fixture
def streaming_callback():
    """Create a StreamingAuditCallback with a mock session factory and a queue."""
    run_id = uuid.uuid4()
    queue = asyncio.Queue()

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    @asynccontextmanager
    async def session_factory():
        yield mock_session

    cb = StreamingAuditCallback(
        run_id=run_id,
        session_factory=session_factory,
        event_queue=queue,
    )
    return cb, queue, mock_session


@pytest.mark.asyncio
async def test_on_llm_start_defers_event(streaming_callback):
    """llm_start should be deferred — no event pushed until llm_end."""
    cb, queue, _ = streaming_callback

    await cb.on_llm_start(
        serialized={},
        prompts=["test"],
        run_id=uuid.uuid4(),
    )

    # Event is deferred, not pushed yet
    assert queue.empty()
    assert cb._pending_llm_start is True


@pytest.mark.asyncio
async def test_on_chat_model_start_defers_event(streaming_callback):
    """on_chat_model_start should also defer the event."""
    cb, queue, _ = streaming_callback

    await cb.on_chat_model_start(
        serialized={},
        messages=[[]],
        run_id=uuid.uuid4(),
    )

    assert queue.empty()
    assert cb._pending_llm_start is True


@pytest.mark.asyncio
async def test_on_llm_end_writes_step_and_pushes_event(streaming_callback):
    cb, queue, mock_session = streaming_callback
    llm_run_id = uuid.uuid4()

    # Simulate start (deferred)
    await cb.on_llm_start(serialized={}, prompts=["test"], run_id=llm_run_id)
    assert queue.empty()

    # Simulate end with text response
    response = MagicMock()
    response.llm_output = {"token_usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}
    gen = MagicMock()
    gen.text = "Hello from LLM"
    gen.message = MagicMock()
    gen.message.tool_calls = []  # no tool calls — text response
    response.generations = [[gen]]

    await cb.on_llm_end(response=response, run_id=llm_run_id)

    # Should have written to DB
    assert mock_session.add.called
    assert mock_session.commit.called

    # Should have pushed deferred llm_start THEN llm_end
    start_event = queue.get_nowait()
    assert start_event["event"] == "llm_start"
    assert start_event["data"]["step_order"] == 1

    end_event = queue.get_nowait()
    assert end_event["event"] == "llm_end"
    assert end_event["data"]["type"] == "llm_call"
    assert end_event["data"]["output"]["response"] == "Hello from LLM"
    assert end_event["data"]["token_usage"]["total_tokens"] == 15
    assert end_event["data"]["duration_ms"] is not None


@pytest.mark.asyncio
async def test_on_llm_end_skips_tool_call_response(streaming_callback):
    """When LLM response is a tool call, don't emit llm_start or llm_end."""
    cb, queue, mock_session = streaming_callback
    llm_run_id = uuid.uuid4()

    await cb.on_llm_start(serialized={}, prompts=["test"], run_id=llm_run_id)

    # Simulate end with tool call (no text)
    response = MagicMock()
    response.llm_output = {}
    gen = MagicMock()
    gen.text = ""
    gen.message = MagicMock()
    gen.message.tool_calls = [{"name": "es_search", "args": {"query": "test"}}]
    response.generations = [[gen]]

    await cb.on_llm_end(response=response, run_id=llm_run_id)

    # No events should be pushed (both start and end suppressed)
    assert queue.empty()
    assert cb._pending_llm_start is False


@pytest.mark.asyncio
async def test_on_tool_start_writes_and_pushes(streaming_callback):
    cb, queue, mock_session = streaming_callback

    await cb.on_tool_start(
        serialized={"name": "es_search"},
        input_str='{"query": "test"}',
        run_id=uuid.uuid4(),
    )

    assert mock_session.add.called
    event = queue.get_nowait()
    assert event["event"] == "tool_start"
    assert event["data"]["tool_name"] == "es_search"


@pytest.mark.asyncio
async def test_on_tool_end_writes_and_pushes(streaming_callback):
    cb, queue, mock_session = streaming_callback
    tool_run_id = uuid.uuid4()

    await cb.on_tool_start(
        serialized={"name": "es_search"},
        input_str="test",
        run_id=tool_run_id,
    )
    queue.get_nowait()  # consume tool_start
    mock_session.reset_mock()

    await cb.on_tool_end(output='{"hits": 5}', run_id=tool_run_id)

    assert mock_session.add.called
    event = queue.get_nowait()
    assert event["event"] == "tool_end"
    assert event["data"]["duration_ms"] is not None


@pytest.mark.asyncio
async def test_on_tool_error_writes_and_pushes(streaming_callback):
    cb, queue, mock_session = streaming_callback
    tool_run_id = uuid.uuid4()

    await cb.on_tool_start(
        serialized={"name": "sql_query"},
        input_str="SELECT 1",
        run_id=tool_run_id,
    )
    queue.get_nowait()  # consume tool_start
    mock_session.reset_mock()

    await cb.on_tool_error(error=RuntimeError("db down"), run_id=tool_run_id)

    assert mock_session.add.called
    event = queue.get_nowait()
    assert event["event"] == "tool_error"
    assert "db down" in event["data"]["error"]


@pytest.mark.asyncio
async def test_step_counter_increments(streaming_callback):
    cb, queue, _ = streaming_callback

    await cb.on_tool_start(
        serialized={"name": "a"}, input_str="x", run_id=uuid.uuid4()
    )
    await cb.on_tool_start(
        serialized={"name": "b"}, input_str="y", run_id=uuid.uuid4()
    )

    e1 = queue.get_nowait()
    e2 = queue.get_nowait()
    assert e1["data"]["step_order"] == 1
    assert e2["data"]["step_order"] == 2
    assert cb._step_counter == 2


# ---------------------------------------------------------------------------
# execute_agent_streaming tests
# ---------------------------------------------------------------------------


def _make_agent_config():
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


def _make_session_factory(run_id):
    session = AsyncMock()
    run_obj = MagicMock()
    run_obj.id = run_id

    call_count = 0

    async def _execute(stmt, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        result.scalar_one_or_none.return_value = _make_agent_config() if call_count == 1 else run_obj
        result.scalar_one.return_value = run_obj
        return result

    session.execute = _execute
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock(side_effect=lambda obj, **kw: setattr(obj, "id", run_id))

    @asynccontextmanager
    async def factory():
        yield session

    return factory


@pytest.mark.asyncio
async def test_streaming_executor_success():
    """Test that streaming executor pushes run_started and run_completed."""
    from langchain_core.messages import AIMessage

    run_id = uuid.uuid4()
    queue = asyncio.Queue()
    cancelled = asyncio.Event()
    agent_config = _make_agent_config()

    mock_result = {"messages": [AIMessage(content="Stream result")]}

    with patch(
        "umbrella_agents.executor.load_agent_config",
        new_callable=AsyncMock,
        return_value=agent_config,
    ), patch("umbrella_agents.executor.create_react_agent") as mock_create:
        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock(return_value=mock_result)
        mock_create.return_value = mock_graph

        await execute_agent_streaming(
            agent_id=agent_config.id,
            user_input="Test streaming",
            triggered_by=uuid.uuid4(),
            run_id=run_id,
            session_factory=_make_session_factory(run_id),
            es_client=AsyncMock(),
            event_queue=queue,
            cancelled=cancelled,
        )

    events = []
    while not queue.empty():
        events.append(queue.get_nowait())

    # Should end with None sentinel
    assert events[-1] is None
    events = [e for e in events if e is not None]

    event_types = [e["event"] for e in events]
    assert "run_started" in event_types
    assert "run_completed" in event_types

    completed = next(e for e in events if e["event"] == "run_completed")
    assert completed["data"]["status"] == "completed"


@pytest.mark.asyncio
async def test_streaming_executor_failure():
    """Test that a failed execution pushes run_failed."""
    run_id = uuid.uuid4()
    queue = asyncio.Queue()
    cancelled = asyncio.Event()
    agent_config = _make_agent_config()

    with patch(
        "umbrella_agents.executor.load_agent_config",
        new_callable=AsyncMock,
        return_value=agent_config,
    ), patch("umbrella_agents.executor.create_react_agent") as mock_create:
        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock(side_effect=RuntimeError("boom"))
        mock_create.return_value = mock_graph

        await execute_agent_streaming(
            agent_id=agent_config.id,
            user_input="Fail please",
            triggered_by=uuid.uuid4(),
            run_id=run_id,
            session_factory=_make_session_factory(run_id),
            es_client=AsyncMock(),
            event_queue=queue,
            cancelled=cancelled,
        )

    events = []
    while not queue.empty():
        events.append(queue.get_nowait())

    events = [e for e in events if e is not None]
    event_types = [e["event"] for e in events]
    assert "run_started" in event_types
    assert "run_failed" in event_types

    failed = next(e for e in events if e["event"] == "run_failed")
    assert "boom" in failed["data"]["error_message"]


@pytest.mark.asyncio
async def test_streaming_executor_cancelled():
    """Test that a pre-cancelled run pushes run_cancelled."""
    run_id = uuid.uuid4()
    queue = asyncio.Queue()
    cancelled = asyncio.Event()
    cancelled.set()  # pre-cancel
    agent_config = _make_agent_config()

    with patch(
        "umbrella_agents.executor.load_agent_config",
        new_callable=AsyncMock,
        return_value=agent_config,
    ), patch("umbrella_agents.executor.create_react_agent") as mock_create:
        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock(return_value={"messages": []})
        mock_create.return_value = mock_graph

        await execute_agent_streaming(
            agent_id=agent_config.id,
            user_input="Cancel me",
            triggered_by=uuid.uuid4(),
            run_id=run_id,
            session_factory=_make_session_factory(run_id),
            es_client=AsyncMock(),
            event_queue=queue,
            cancelled=cancelled,
        )

    events = []
    while not queue.empty():
        events.append(queue.get_nowait())

    events = [e for e in events if e is not None]
    event_types = [e["event"] for e in events]
    assert "run_cancelled" in event_types


@pytest.mark.asyncio
async def test_streaming_executor_always_pushes_sentinel():
    """The sentinel None is always pushed, even on fatal errors."""
    run_id = uuid.uuid4()
    queue = asyncio.Queue()
    cancelled = asyncio.Event()

    with patch(
        "umbrella_agents.executor.load_agent_config",
        new_callable=AsyncMock,
        side_effect=ValueError("Agent not found"),
    ):
        await execute_agent_streaming(
            agent_id=uuid.uuid4(),
            user_input="whatever",
            triggered_by=uuid.uuid4(),
            run_id=run_id,
            session_factory=_make_session_factory(run_id),
            es_client=AsyncMock(),
            event_queue=queue,
            cancelled=cancelled,
        )

    events = []
    while not queue.empty():
        events.append(queue.get_nowait())

    assert events[-1] is None
    non_none = [e for e in events if e is not None]
    assert any(e["event"] == "run_failed" for e in non_none)
