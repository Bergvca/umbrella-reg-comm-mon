"""Agent execution endpoints — proxy to runtime + run history."""

from __future__ import annotations

import uuid
from typing import Annotated

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.responses import StreamingResponse

from umbrella_ui.auth.rbac import get_current_user_sse, require_role
from umbrella_ui.config import Settings
from umbrella_ui.db.models.agent import AgentRun, AgentRunStep
from umbrella_ui.deps import get_agent_session, get_settings
from umbrella_ui.schemas.agent import RunCreate, RunOut, RunStepOut
from umbrella_ui.schemas.common import PaginatedResponse

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/agent-runs", tags=["agent-runs"])


def _run_to_out(run: AgentRun, include_steps: bool = False) -> RunOut:
    steps = None
    if include_steps and run.steps:
        steps = [
            RunStepOut(
                id=s.id,
                step_order=s.step_order,
                step_type=s.step_type,
                tool_name=s.tool_name,
                input=s.input,
                output=s.output,
                token_usage=s.token_usage,
                duration_ms=s.duration_ms,
                created_at=s.created_at,
            )
            for s in run.steps
        ]

    return RunOut(
        id=run.id,
        agent_id=run.agent_id,
        status=run.status,
        input=run.input,
        output=run.output,
        error_message=run.error_message,
        token_usage=run.token_usage,
        iterations=run.iterations,
        duration_ms=run.duration_ms,
        triggered_by=run.triggered_by,
        created_at=run.created_at,
        completed_at=run.completed_at,
        steps=steps,
    )


@router.post("", response_model=RunOut, status_code=status.HTTP_201_CREATED)
async def execute_agent(
    body: RunCreate,
    session: Annotated[AsyncSession, Depends(get_agent_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    current_user: Annotated[dict, Depends(require_role("reviewer"))],
):
    """Proxy execution to the agent runtime."""
    execute_url = f"{settings.agents_base_url}/execute"

    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await client.post(
                execute_url,
                json={
                    "agent_id": str(body.agent_id),
                    "input": body.input,
                    "triggered_by": str(current_user["id"]),
                },
            )
            resp.raise_for_status()
            result = resp.json()
    except httpx.HTTPStatusError as exc:
        detail = "Agent execution failed"
        if exc.response.status_code == 404:
            detail = exc.response.json().get("detail", "Agent not found")
        logger.error("agent_execute_failed", status=exc.response.status_code)
        raise HTTPException(status_code=exc.response.status_code, detail=detail)
    except httpx.RequestError as exc:
        logger.error("agent_runtime_unreachable", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Agent runtime unreachable",
        )

    # Fetch the created run from the DB so we return the full object
    run_id = uuid.UUID(result["run_id"])
    stmt = select(AgentRun).where(AgentRun.id == run_id).options(selectinload(AgentRun.steps))
    run = (await session.execute(stmt)).scalar_one_or_none()
    if run is None:
        # Runtime returned success but run not in DB yet — return runtime result directly
        return RunOut(
            id=run_id,
            agent_id=body.agent_id,
            status=result["status"],
            input={"prompt": body.input},
            output=result.get("output"),
            error_message=result.get("error_message"),
            token_usage=None,
            iterations=result.get("iterations"),
            duration_ms=result.get("duration_ms"),
            triggered_by=current_user["id"],
            created_at=None,  # type: ignore[arg-type]
            completed_at=None,
        )

    return _run_to_out(run, include_steps=True)


@router.get("", response_model=PaginatedResponse[RunOut])
async def list_runs(
    session: Annotated[AsyncSession, Depends(get_agent_session)],
    _user: Annotated[dict, Depends(require_role("reviewer"))],
    agent_id: uuid.UUID | None = Query(default=None),
    run_status: str | None = Query(default=None, alias="status"),
    triggered_by: uuid.UUID | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
):
    base = select(AgentRun)
    if agent_id:
        base = base.where(AgentRun.agent_id == agent_id)
    if run_status:
        base = base.where(AgentRun.status == run_status)
    if triggered_by:
        base = base.where(AgentRun.triggered_by == triggered_by)

    total = (await session.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    stmt = base.offset(offset).limit(limit).order_by(AgentRun.created_at.desc())
    rows = (await session.execute(stmt)).scalars().all()

    return PaginatedResponse(
        items=[_run_to_out(r) for r in rows],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/{run_id}", response_model=RunOut)
async def get_run(
    run_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_agent_session)],
    _user: Annotated[dict, Depends(require_role("reviewer"))],
):
    stmt = select(AgentRun).where(AgentRun.id == run_id).options(selectinload(AgentRun.steps))
    run = (await session.execute(stmt)).scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return _run_to_out(run, include_steps=True)


# ---------------------------------------------------------------------------
# Streaming endpoints
# ---------------------------------------------------------------------------


@router.post("/stream", status_code=status.HTTP_201_CREATED)
async def execute_agent_stream(
    body: RunCreate,
    settings: Annotated[Settings, Depends(get_settings)],
    current_user: Annotated[dict, Depends(require_role("reviewer"))],
):
    """Start a streaming agent execution. Returns run_id immediately."""
    url = f"{settings.agents_base_url}/execute-stream"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                url,
                json={
                    "agent_id": str(body.agent_id),
                    "input": body.input,
                    "triggered_by": str(current_user["id"]),
                },
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as exc:
        detail = "Agent execution failed"
        if exc.response.status_code == 429:
            detail = "Too many concurrent agent runs"
        elif exc.response.status_code == 404:
            detail = exc.response.json().get("detail", "Agent not found")
        logger.error("agent_stream_failed", status=exc.response.status_code)
        raise HTTPException(status_code=exc.response.status_code, detail=detail)
    except httpx.RequestError as exc:
        logger.error("agent_runtime_unreachable", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Agent runtime unreachable",
        )


@router.get("/{run_id}/stream")
async def stream_run(
    run_id: uuid.UUID,
    settings: Annotated[Settings, Depends(get_settings)],
    _user: Annotated[dict, Depends(get_current_user_sse)],
):
    """Proxy SSE stream from the agent runtime."""
    url = f"{settings.agents_base_url}/runs/{run_id}/stream"

    async def proxy_stream():
        async with httpx.AsyncClient(timeout=None) as client:
            try:
                async with client.stream("GET", url) as resp:
                    if resp.status_code == 404:
                        return
                    async for chunk in resp.aiter_text():
                        yield chunk
            except httpx.RequestError as exc:
                logger.error("sse_proxy_error", run_id=str(run_id), error=str(exc))

    return StreamingResponse(
        proxy_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{run_id}/cancel")
async def cancel_run(
    run_id: uuid.UUID,
    settings: Annotated[Settings, Depends(get_settings)],
    _user: Annotated[dict, Depends(require_role("supervisor"))],
):
    """Proxy cancellation to the agent runtime."""
    url = f"{settings.agents_base_url}/runs/{run_id}/cancel"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail="Run not found or already completed")
    except httpx.RequestError as exc:
        logger.error("agent_runtime_unreachable", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Agent runtime unreachable",
        )
