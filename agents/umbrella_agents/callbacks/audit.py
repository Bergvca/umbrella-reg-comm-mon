"""LangChain callback handler that logs run steps to the database."""

from __future__ import annotations

import time
import uuid
from typing import Any

import structlog
from langchain_core.callbacks import AsyncCallbackHandler
from sqlalchemy.ext.asyncio import async_sessionmaker

from umbrella_agents.db.models import RunStep

logger = structlog.get_logger()


class AuditCallbackHandler(AsyncCallbackHandler):
    """Records each LLM call, tool call, and tool result as a ``run_step`` row."""

    def __init__(self, run_id: uuid.UUID, session_factory: async_sessionmaker) -> None:
        super().__init__()
        self.run_id = run_id
        self.session_factory = session_factory
        self._step_counter = 0
        self._timers: dict[str, float] = {}
        self._token_usage: dict[str, dict] = {}

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
            logger.warning("audit_write_failed", run_id=str(self.run_id), step_type=step_type, exc_info=True)

    # -- LLM events ----------------------------------------------------------

    async def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: uuid.UUID,
        **kwargs: Any,
    ) -> None:
        self._timers[str(run_id)] = time.monotonic()

    async def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[Any]],
        *,
        run_id: uuid.UUID,
        **kwargs: Any,
    ) -> None:
        self._timers[str(run_id)] = time.monotonic()

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

        # Extract response text
        output_text = ""
        if response.generations:
            gen = response.generations[0]
            if gen:
                output_text = gen[0].text if hasattr(gen[0], "text") else str(gen[0])

        await self._write_step(
            step_type="llm_call",
            input_data={"type": "llm_call"},
            output_data={"response": output_text[:2000]},
            token_usage=token_usage,
            duration_ms=duration_ms,
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

        await self._write_step(
            step_type="tool_call",
            tool_name=tool_name,
            input_data={"tool_input": input_str[:2000]},
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

        await self._write_step(
            step_type="tool_result",
            input_data={"type": "tool_result"},
            output_data={"result": str(output)[:5000]},
            duration_ms=duration_ms,
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

        await self._write_step(
            step_type="tool_result",
            input_data={"type": "tool_error"},
            output_data={"error": str(error)[:2000]},
            duration_ms=duration_ms,
        )
