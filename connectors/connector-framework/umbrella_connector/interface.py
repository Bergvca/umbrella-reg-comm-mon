"""ConnectorInterface — the ABC that every connector must implement."""

from __future__ import annotations

import abc
from collections.abc import AsyncIterator

from .models import BackfillRequest, RawMessage


class ConnectorInterface(abc.ABC):
    """Abstract interface for an Umbrella connector plugin.

    Concrete connectors implement ``ingest`` (live ingestion) and
    optionally ``backfill`` (historical replay).  Both are async
    generators that yield :class:`RawMessage` instances — the framework
    consumes them and handles delivery, retry, and dead-letter routing.
    """

    @abc.abstractmethod
    def ingest(self) -> AsyncIterator[RawMessage]:
        """Yield raw messages from the live data source.

        This is an async generator that runs indefinitely (until the
        connector is shut down).  It should yield each captured message
        as a :class:`RawMessage`.
        """
        ...

    async def health_check(self) -> dict[str, object]:
        """Return connector-specific health details.

        Override to include source-system connectivity checks, queue
        depths, last-poll timestamps, etc.  The dict is included in the
        ``/health`` response.
        """
        return {}

    def backfill(self, request: BackfillRequest) -> AsyncIterator[RawMessage]:
        """Yield raw messages for a historical backfill window.

        Override to support replaying messages from the source system
        for a given time range.  The default raises ``NotImplementedError``.
        """
        raise NotImplementedError(f"{type(self).__name__} does not support backfill")
