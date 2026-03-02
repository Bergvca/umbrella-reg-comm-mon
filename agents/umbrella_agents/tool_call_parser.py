"""Parse text-based tool calls from LLM responses.

Some models (e.g. DeepSeek on Azure) don't support the structured
``tool_calls`` response format.  Instead they output tool invocations as
plain text like::

    es_search {"query": "oil futures", "filters": {}}

This module wraps a LangChain chat model and post-processes its output so
that text-based tool calls are converted to proper ``AIMessage.tool_calls``,
allowing LangGraph's ``create_react_agent`` to execute them.
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any, Sequence

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import RunnableConfig

import structlog

logger = structlog.get_logger()

# Matches: tool_name {json...} or tool_name({json...})
# Captures the tool name and the JSON body.
_TOOL_CALL_RE = re.compile(
    r"(?:^|\n)\s*(\w+)\s*\(?\s*(\{.*?\})\s*\)?\s*$",
    re.DOTALL,
)


def _extract_text_tool_calls(
    text: str,
    known_tools: set[str],
) -> list[dict[str, Any]]:
    """Extract tool calls from plain text, returning them in LangChain format."""
    calls: list[dict[str, Any]] = []
    for match in _TOOL_CALL_RE.finditer(text):
        tool_name = match.group(1)
        json_str = match.group(2)
        if tool_name not in known_tools:
            continue
        try:
            args = json.loads(json_str)
        except json.JSONDecodeError:
            continue
        calls.append({
            "name": tool_name,
            "args": args,
            "id": f"call_{uuid.uuid4().hex[:12]}",
            "type": "tool_call",
        })
    return calls


def _strip_think_tags(text: str) -> str:
    """Remove <think>...</think> blocks from DeepSeek responses."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


class TextToolCallingWrapper(BaseChatModel):
    """Wraps a chat model to parse text-based tool calls into structured ones.

    If the underlying model returns an ``AIMessage`` without ``tool_calls``
    but the text contains a recognisable tool invocation, this wrapper
    converts it so LangGraph can execute the tool.

    When the model already returns proper ``tool_calls``, this wrapper is a
    no-op pass-through.

    .. note::

       After ``bind_tools`` the delegate is typically a ``RunnableBinding``.
       We must call ``delegate.ainvoke()`` (not ``delegate._agenerate()``)
       so the binding properly merges the ``tools`` kwarg into the LLM
       request.
    """

    delegate: Any  # BaseChatModel or RunnableBinding
    known_tool_names: set[str] = set()

    model_config = {"arbitrary_types_allowed": True}

    @property
    def _llm_type(self) -> str:
        return "text-tool-calling-wrapper"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        raise NotImplementedError("Use async version")

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        # Use ainvoke on the delegate so RunnableBinding merges kwargs
        # (e.g. tools) correctly.  ainvoke returns a BaseMessage, so we
        # wrap it back into a ChatResult.
        response = await self.delegate.ainvoke(messages, **kwargs)
        processed = self._post_process_message(response)
        return ChatResult(generations=[ChatGeneration(message=processed)])

    def _post_process_message(self, msg: BaseMessage) -> BaseMessage:
        """If the message has no tool_calls but text looks like one, parse it."""
        if not isinstance(msg, AIMessage):
            return msg

        # Already has structured tool calls — pass through.
        if msg.tool_calls:
            return msg

        raw_content = msg.content or ""
        if isinstance(raw_content, list):
            # Multi-part content (e.g. text + tool-use blocks from some models).
            # Extract only the text parts for tool-call parsing.
            text = " ".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in raw_content
            )
        else:
            text = raw_content
        clean_text = _strip_think_tags(text)
        calls = _extract_text_tool_calls(clean_text, self.known_tool_names)

        if not calls:
            return msg

        logger.info(
            "parsed_text_tool_calls",
            num_calls=len(calls),
            tools=[c["name"] for c in calls],
        )

        return AIMessage(content="", tool_calls=calls)

    # Keep legacy ChatResult-level helper for direct unit-test usage.
    def _post_process(self, result: ChatResult) -> ChatResult:
        """Post-process a ChatResult (legacy helper for tests)."""
        if not result.generations:
            return result
        gen = result.generations[0]
        processed = self._post_process_message(gen.message)
        if processed is gen.message:
            return result
        return ChatResult(generations=[ChatGeneration(message=processed)])

    def bind_tools(
        self,
        tools: Sequence[Any],
        **kwargs: Any,
    ) -> TextToolCallingWrapper:
        """Bind tools to the delegate and record tool names for parsing."""
        bound_delegate = self.delegate.bind_tools(tools, **kwargs)
        tool_names = set()
        for tool in tools:
            if isinstance(tool, dict):
                name = tool.get("function", {}).get("name") or tool.get("name")
                if name:
                    tool_names.add(name)
            elif hasattr(tool, "name"):
                tool_names.add(tool.name)
        return TextToolCallingWrapper(
            delegate=bound_delegate,
            known_tool_names=tool_names,
        )
