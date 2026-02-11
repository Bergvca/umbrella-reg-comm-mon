"""Graceful shutdown handling via SIGTERM / SIGINT."""

from __future__ import annotations

import asyncio
import signal

import structlog

logger = structlog.get_logger()


def install_signal_handlers(shutdown_event: asyncio.Event) -> None:
    """Register SIGTERM and SIGINT handlers that set *shutdown_event*.

    Call this once from the running event loop.  When a signal is
    received the event is set, which unblocks any ``await
    shutdown_event.wait()`` calls in the connector run-loop.
    """
    loop = asyncio.get_running_loop()

    def _handle(sig: signal.Signals) -> None:
        logger.info("shutdown_signal_received", signal=sig.name)
        shutdown_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _handle, sig)
