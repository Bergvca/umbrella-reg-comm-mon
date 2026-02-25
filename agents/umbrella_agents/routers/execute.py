"""Agent execution endpoint."""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from umbrella_agents.executor import execute_agent

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
