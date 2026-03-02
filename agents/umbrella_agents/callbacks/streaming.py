"""LangChain callback handler that logs steps to the DB and pushes SSE events."""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any

import structlog
from langchain_core.callbacks import AsyncCallbackHandler
from sqlalchemy.ext.asyncio import async_sessionmaker

from umbrella_agents.db.models import RunStep

logger = structlog.get_logger()


class StreamingAuditCallback(AsyncCallbackHandler):
    """Records each step as a ``run_step`` row AND pushes events to an asyncio.Queue.

    This is the streaming counterpart of ``AuditCallbackHandler``.  The queue
    is consumed by the SSE endpoint so that the frontend receives events in
    real time.
    """

    def __init__(
        self,
        run_id: uuid.UUID,
        session_factory: async_sessionmaker,
        event_queue: asyncio.Queue,
    ) -> None:
        super().__init__()
        self.run_id = run_id
        self.session_factory = session_factory
        self.event_queue = event_queue
        self._step_counter = 0
        self._timers: dict[str, float] = {}
        self._pending_llm_start = False

    def _next_step(self) -> int:
        self._step_counter += 1
        return self._step_counter

    async def _write_step(
        self,
        step_type: str,
        input_data: dict,
        output_data: dict | None = None,
        tool_name: str | None = None,
        token_usage: dict | None = None,
        duration_ms: int | None = None,
    ) -> None:
        step = RunStep(
            run_id=self.run_id,
            step_order=self._next_step(),
            step_type=step_type,
            tool_name=tool_name,
            input=input_data,
            output=output_data,
            token_usage=token_usage,
            duration_ms=duration_ms,
        )
        try:
            async with self.session_factory() as session:
                session.add(step)
                await session.commit()
        except Exception:
            logger.warning(
                "audit_write_failed",
                run_id=str(self.run_id),
                step_type=step_type,
                exc_info=True,
            )

    async def _push_event(self, event_type: str, data: dict) -> None:
        try:
            self.event_queue.put_nowait({"event": event_type, "data": data})
        except asyncio.QueueFull:
            logger.warning(
                "event_queue_full",
                run_id=str(self.run_id),
                event=event_type,
            )

    # -- LLM events ----------------------------------------------------------

    async def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: uuid.UUID,
        **kwargs: Any,
    ) -> None:
        # For chat models LangChain fires both on_chat_model_start and
        # on_llm_start.  Only record the timer once per run_id.
        key = str(run_id)
        if key in self._timers:
            return
        self._timers[key] = time.monotonic()
        # Defer the llm_start event — only emit it in on_llm_end if the
        # LLM produced text output (not a tool call).  This avoids showing
        # an empty "LLM" step when the model decides to call a tool.
        self._pending_llm_start = True

    async def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[Any]],
        *,
        run_id: uuid.UUID,
        **kwargs: Any,
    ) -> None:
        key = str(run_id)
        if key in self._timers:
            return
        self._timers[key] = time.monotonic()
        self._pending_llm_start = True

    async def on_llm_end(
        self,
        response: Any,
        *,
        run_id: uuid.UUID,
        **kwargs: Any,
    ) -> None:
        elapsed = time.monotonic() - self._timers.pop(str(run_id), time.monotonic())
        duration_ms = int(elapsed * 1000)

        token_usage = None
        if hasattr(response, "llm_output") and response.llm_output:
            usage = response.llm_output.get("token_usage")
            if usage:
                token_usage = dict(usage)

        output_text = ""
        if response.generations:
            gen = response.generations[0]
            if gen:
                msg = gen[0].message if hasattr(gen[0], "message") else None
                # When the LLM emits a tool call, content is empty — skip
                # emitting a visible step since the tool_start/tool_end events
                # already cover it.  This also removes the pending llm_start.
                if msg and hasattr(msg, "tool_calls") and msg.tool_calls:
                    # Pop the matching llm_start so the UI doesn't show a
                    # dangling "Thinking..." step with no llm_end.
                    self._pending_llm_start = False
                    return
                output_text = gen[0].text if hasattr(gen[0], "text") else str(gen[0])

        output_data = {"response": output_text[:2000]}

        # Emit the deferred llm_start now that we know it's a real text response
        if self._pending_llm_start:
            step_order = self._step_counter + 1
            await self._push_event("llm_start", {"step_order": step_order, "type": "llm_call"})
            self._pending_llm_start = False

        await self._write_step(
            step_type="llm_call",
            input_data={"type": "llm_call"},
            output_data=output_data,
            token_usage=token_usage,
            duration_ms=duration_ms,
        )
        await self._push_event(
            "llm_end",
            {
                "step_order": self._step_counter,
                "type": "llm_call",
                "output": output_data,
                "token_usage": token_usage,
                "duration_ms": duration_ms,
            },
        )

    # -- Tool events ----------------------------------------------------------

    async def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: uuid.UUID,
        **kwargs: Any,
    ) -> None:
        self._timers[str(run_id)] = time.monotonic()
        tool_name = serialized.get("name", "unknown")
        input_data = {"tool_input": input_str[:2000]}

        await self._write_step(
            step_type="tool_call",
            tool_name=tool_name,
            input_data=input_data,
        )
        await self._push_event(
            "tool_start",
            {
                "step_order": self._step_counter,
                "type": "tool_call",
                "tool_name": tool_name,
                "input": input_data,
            },
        )

    async def on_tool_end(
        self,
        output: str,
        *,
        run_id: uuid.UUID,
        **kwargs: Any,
    ) -> None:
        elapsed = time.monotonic() - self._timers.pop(str(run_id), time.monotonic())
        duration_ms = int(elapsed * 1000)
        output_data = {"result": str(output)[:5000]}

        await self._write_step(
            step_type="tool_result",
            input_data={"type": "tool_result"},
            output_data=output_data,
            duration_ms=duration_ms,
        )
        await self._push_event(
            "tool_end",
            {
                "step_order": self._step_counter,
                "type": "tool_result",
                "tool_name": None,
                "output": output_data,
                "duration_ms": duration_ms,
            },
        )

    async def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: uuid.UUID,
        **kwargs: Any,
    ) -> None:
        elapsed = time.monotonic() - self._timers.pop(str(run_id), time.monotonic())
        duration_ms = int(elapsed * 1000)
        output_data = {"error": str(error)[:2000]}

        await self._write_step(
            step_type="tool_result",
            input_data={"type": "tool_error"},
            output_data=output_data,
            duration_ms=duration_ms,
        )
        await self._push_event(
            "tool_error",
            {
                "step_order": self._step_counter,
                "type": "tool_error",
                "tool_name": None,
                "error": str(error)[:2000],
                "duration_ms": duration_ms,
            },
        )
