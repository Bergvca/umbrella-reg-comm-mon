"""SSE streaming and run cancellation endpoints."""

from __future__ import annotations

import asyncio
import json
import uuid

import structlog
from fastapi import APIRouter, HTTPException, Request, status
from sse_starlette.sse import EventSourceResponse

logger = structlog.get_logger()

router = APIRouter(tags=["streaming"])

_HEARTBEAT_INTERVAL_S = 15


@router.get("/runs/{run_id}/stream")
async def stream_run(run_id: uuid.UUID, request: Request):
    """SSE endpoint that streams execution events for a run."""
    registry = request.app.state.run_registry
    managed = registry.get(run_id)

    if managed is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found or already completed",
        )

    async def event_generator():
        try:
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    break

                try:
                    event = await asyncio.wait_for(
                        managed.queue.get(),
                        timeout=_HEARTBEAT_INTERVAL_S,
                    )
                except asyncio.TimeoutError:
                    yield {"event": "heartbeat", "data": "{}"}
                    continue

                if event is None:
                    break  # sentinel — stream finished

                yield {
                    "event": event["event"],
                    "data": json.dumps(event["data"], default=str),
                }
        except asyncio.CancelledError:
            pass

    return EventSourceResponse(event_generator())


@router.post("/runs/{run_id}/cancel")
async def cancel_run(run_id: uuid.UUID, request: Request):
    """Request cancellation of a running agent."""
    registry = request.app.state.run_registry
    if not registry.cancel(run_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found or already completed",
        )
    return {"status": "cancelling"}
