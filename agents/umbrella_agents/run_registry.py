"""Registry for in-flight agent runs with their event queues and background tasks."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field

import structlog

logger = structlog.get_logger()

_CLEANUP_DELAY_S = 60


@dataclass
class ManagedRun:
    """Tracks a single in-flight agent run."""

    run_id: uuid.UUID
    queue: asyncio.Queue
    task: asyncio.Task
    cancelled: asyncio.Event = field(default_factory=asyncio.Event)


class RunRegistry:
    """Singleton registry for in-flight agent runs.

    Manages background execution tasks and their associated event queues
    so that SSE endpoints can read live events.
    """

    def __init__(self) -> None:
        self._runs: dict[uuid.UUID, ManagedRun] = {}

    def register(
        self,
        run_id: uuid.UUID,
        task: asyncio.Task,
        queue: asyncio.Queue,
        cancelled: asyncio.Event,
    ) -> ManagedRun:
        managed = ManagedRun(
            run_id=run_id,
            queue=queue,
            task=task,
            cancelled=cancelled,
        )
        self._runs[run_id] = managed
        logger.info("run_registered", run_id=str(run_id))
        return managed

    def get(self, run_id: uuid.UUID) -> ManagedRun | None:
        return self._runs.get(run_id)

    def cancel(self, run_id: uuid.UUID) -> bool:
        managed = self._runs.get(run_id)
        if managed is None:
            return False
        managed.cancelled.set()
        logger.info("run_cancel_requested", run_id=str(run_id))
        return True

    def remove(self, run_id: uuid.UUID) -> None:
        self._runs.pop(run_id, None)
        logger.info("run_removed", run_id=str(run_id))

    def schedule_cleanup(self, run_id: uuid.UUID) -> None:
        """Remove the run from the registry after a grace period."""

        async def _delayed_remove() -> None:
            await asyncio.sleep(_CLEANUP_DELAY_S)
            self.remove(run_id)

        asyncio.create_task(_delayed_remove())

    @property
    def active_count(self) -> int:
        return len(self._runs)

    async def cancel_all(self) -> None:
        """Cancel all in-flight runs (used during shutdown)."""
        for managed in list(self._runs.values()):
            managed.cancelled.set()
            managed.task.cancel()
        self._runs.clear()
