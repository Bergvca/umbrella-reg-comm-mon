"""Tests for the text-based tool call parser."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from umbrella_agents.tool_call_parser import (
    TextToolCallingWrapper,
    _extract_text_tool_calls,
    _strip_think_tags,
)


# ---------------------------------------------------------------------------
# _strip_think_tags
# ---------------------------------------------------------------------------


def test_strip_think_tags():
    text = '<think>Some reasoning here about the query.</think>es_search {"query": "oil"}'
    assert _strip_think_tags(text) == 'es_search {"query": "oil"}'


def test_strip_think_tags_multiline():
    text = (
        "<think>\nLet me think about this.\n"
        "We need to search for oil futures.\n"
        "</think>\n"
        'es_search {"query": "oil futures"}'
    )
    result = _strip_think_tags(text)
    assert "<think>" not in result
    assert "es_search" in result


def test_strip_think_tags_no_tags():
    text = 'es_search {"query": "test"}'
    assert _strip_think_tags(text) == text


# ---------------------------------------------------------------------------
# _extract_text_tool_calls
# ---------------------------------------------------------------------------


def test_extract_single_tool_call():
    text = 'es_search {"query": "oil futures", "filters": {}}'
    calls = _extract_text_tool_calls(text, {"es_search"})
    assert len(calls) == 1
    assert calls[0]["name"] == "es_search"
    assert calls[0]["args"] == {"query": "oil futures", "filters": {}}
    assert calls[0]["type"] == "tool_call"
    assert calls[0]["id"].startswith("call_")


def test_extract_with_parentheses():
    text = 'es_search({"query": "test"})'
    calls = _extract_text_tool_calls(text, {"es_search"})
    assert len(calls) == 1
    assert calls[0]["args"] == {"query": "test"}


def test_extract_ignores_unknown_tools():
    text = 'unknown_tool {"query": "test"}'
    calls = _extract_text_tool_calls(text, {"es_search"})
    assert len(calls) == 0


def test_extract_ignores_invalid_json():
    text = 'es_search {not valid json}'
    calls = _extract_text_tool_calls(text, {"es_search"})
    assert len(calls) == 0


def test_extract_with_preceding_text():
    text = (
        "Let me search for that.\n"
        'es_search {"query": "oil futures", "filters": {}}'
    )
    calls = _extract_text_tool_calls(text, {"es_search"})
    assert len(calls) == 1
    assert calls[0]["name"] == "es_search"


def test_extract_with_size_param():
    text = 'es_search {"query": "oil", "index": "messages-*", "filters": {}, "size": 10}'
    calls = _extract_text_tool_calls(text, {"es_search"})
    assert len(calls) == 1
    assert calls[0]["args"]["size"] == 10


# ---------------------------------------------------------------------------
# TextToolCallingWrapper._post_process
# ---------------------------------------------------------------------------


def test_post_process_passes_through_structured_tool_calls():
    """When AIMessage already has tool_calls, don't modify it."""
    wrapper = TextToolCallingWrapper(
        delegate=MagicMock(),
        known_tool_names={"es_search"},
    )

    original_calls = [{"name": "es_search", "args": {"query": "test"}, "id": "call_1", "type": "tool_call"}]
    msg = AIMessage(content="", tool_calls=original_calls)
    gen = ChatGeneration(message=msg)
    result = ChatResult(generations=[gen])

    processed = wrapper._post_process(result)
    assert processed.generations[0].message.tool_calls == original_calls


def test_post_process_parses_text_tool_calls():
    """Text-based tool calls should be converted to structured ones."""
    wrapper = TextToolCallingWrapper(
        delegate=MagicMock(),
        known_tool_names={"es_search"},
    )

    msg = AIMessage(content='es_search {"query": "oil futures", "filters": {}}')
    gen = ChatGeneration(message=msg)
    result = ChatResult(generations=[gen])

    processed = wrapper._post_process(result)
    new_msg = processed.generations[0].message
    assert len(new_msg.tool_calls) == 1
    assert new_msg.tool_calls[0]["name"] == "es_search"
    assert new_msg.tool_calls[0]["args"]["query"] == "oil futures"
    assert new_msg.content == ""  # text cleared since it's now a tool call


def test_post_process_with_think_tags():
    """DeepSeek think tags should be stripped before parsing."""
    wrapper = TextToolCallingWrapper(
        delegate=MagicMock(),
        known_tool_names={"es_search"},
    )

    text = (
        "<think>The user wants to search for oil futures. "
        "I should use es_search with query oil futures.</think>"
        'es_search {"query": "oil futures", "filters": {}}'
    )
    msg = AIMessage(content=text)
    gen = ChatGeneration(message=msg)
    result = ChatResult(generations=[gen])

    processed = wrapper._post_process(result)
    new_msg = processed.generations[0].message
    assert len(new_msg.tool_calls) == 1
    assert new_msg.tool_calls[0]["name"] == "es_search"


def test_post_process_no_tool_call_in_text():
    """Plain text responses without tool calls should pass through."""
    wrapper = TextToolCallingWrapper(
        delegate=MagicMock(),
        known_tool_names={"es_search"},
    )

    msg = AIMessage(content="I found 3 results about oil futures.")
    gen = ChatGeneration(message=msg)
    result = ChatResult(generations=[gen])

    processed = wrapper._post_process(result)
    assert processed.generations[0].message.content == "I found 3 results about oil futures."
    assert not processed.generations[0].message.tool_calls


# ---------------------------------------------------------------------------
# TextToolCallingWrapper.bind_tools
# ---------------------------------------------------------------------------


def test_bind_tools_records_tool_names():
    """bind_tools should pass through to delegate and record tool names."""
    delegate = MagicMock()
    bound = MagicMock()
    delegate.bind_tools.return_value = bound

    wrapper = TextToolCallingWrapper(delegate=delegate)

    tool1 = MagicMock()
    tool1.name = "es_search"
    tool2 = MagicMock()
    tool2.name = "sql_query"

    result = wrapper.bind_tools([tool1, tool2])

    assert isinstance(result, TextToolCallingWrapper)
    assert result.known_tool_names == {"es_search", "sql_query"}
    delegate.bind_tools.assert_called_once()


# ---------------------------------------------------------------------------
# TextToolCallingWrapper._agenerate (integration)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_agenerate_delegates_via_ainvoke():
    """Full async flow: delegate.ainvoke returns text tool call, wrapper parses it.

    This tests the critical fix: _agenerate calls delegate.ainvoke() (not
    delegate._agenerate()) so that RunnableBinding merges kwargs properly.
    """
    text_response = 'es_search {"query": "test", "filters": {}}'
    response_msg = AIMessage(content=text_response)

    delegate = MagicMock()
    delegate.ainvoke = AsyncMock(return_value=response_msg)

    wrapper = TextToolCallingWrapper(
        delegate=delegate,
        known_tool_names={"es_search"},
    )

    result = await wrapper._agenerate([])
    # Should have called ainvoke on the delegate, not _agenerate
    delegate.ainvoke.assert_called_once()
    new_msg = result.generations[0].message
    assert len(new_msg.tool_calls) == 1
    assert new_msg.tool_calls[0]["name"] == "es_search"


@pytest.mark.asyncio
async def test_agenerate_passes_through_structured_calls():
    """When delegate returns structured tool_calls, pass through unchanged."""
    original_calls = [{"name": "es_search", "args": {"query": "test"}, "id": "call_1", "type": "tool_call"}]
    response_msg = AIMessage(content="", tool_calls=original_calls)

    delegate = MagicMock()
    delegate.ainvoke = AsyncMock(return_value=response_msg)

    wrapper = TextToolCallingWrapper(
        delegate=delegate,
        known_tool_names={"es_search"},
    )

    result = await wrapper._agenerate([])
    new_msg = result.generations[0].message
    assert new_msg.tool_calls == original_calls
