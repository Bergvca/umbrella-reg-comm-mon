"""Agent execution endpoints (sync and streaming)."""

from __future__ import annotations

import asyncio
import uuid

import structlog
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from umbrella_agents.executor import execute_agent, execute_agent_streaming

logger = structlog.get_logger()

router = APIRouter(tags=["execute"])


class ExecuteRequest(BaseModel):
    agent_id: uuid.UUID
    input: str
    triggered_by: uuid.UUID


class ExecuteResponse(BaseModel):
    run_id: str
    status: str
    output: dict | None = None
    error_message: str | None = None
    iterations: int | None = None
    duration_ms: int | None = None


@router.post("/execute", response_model=ExecuteResponse)
async def execute(body: ExecuteRequest, request: Request):
    """Execute an agent with the given input.

    Loads the agent config from the database, builds a LangGraph ReAct agent,
    executes it, and returns the result.
    """
    settings = request.app.state.settings
    db = request.app.state.db
    es = request.app.state.es

    try:
        result = await execute_agent(
            agent_id=body.agent_id,
            user_input=body.input,
            triggered_by=body.triggered_by,
            session_factory=db.session_factory,
            es_client=es.client,
            timeout=settings.default_timeout,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error("execute_error", error=str(exc), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Agent execution failed unexpectedly",
        )

    return ExecuteResponse(**result)


class ExecuteStreamResponse(BaseModel):
    run_id: str
    status: str


@router.post("/execute-stream", response_model=ExecuteStreamResponse)
async def execute_stream(body: ExecuteRequest, request: Request):
    """Start an agent execution in the background and return the run_id immediately.

    The caller should then connect to ``GET /runs/{run_id}/stream`` to receive
    SSE events as the agent executes.
    """
    settings = request.app.state.settings
    db = request.app.state.db
    es = request.app.state.es
    registry = request.app.state.run_registry

    if registry.active_count >= settings.max_concurrent_runs:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many concurrent agent runs",
        )

    run_id = uuid.uuid4()
    queue: asyncio.Queue = asyncio.Queue(maxsize=200)
    cancelled = asyncio.Event()

    task = asyncio.create_task(
        execute_agent_streaming(
            agent_id=body.agent_id,
            user_input=body.input,
            triggered_by=body.triggered_by,
            run_id=run_id,
            session_factory=db.session_factory,
            es_client=es.client,
            event_queue=queue,
            cancelled=cancelled,
            timeout=settings.default_timeout,
        )
    )

    managed = registry.register(run_id, task, queue, cancelled)

    # Schedule cleanup after task completes
    task.add_done_callback(lambda _: registry.schedule_cleanup(run_id))

    return ExecuteStreamResponse(run_id=str(run_id), status="running")
