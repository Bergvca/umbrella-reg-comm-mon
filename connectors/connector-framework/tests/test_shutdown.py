"""Tests for umbrella_connector.shutdown."""

from __future__ import annotations

import asyncio
import os
import signal

import pytest

from umbrella_connector.shutdown import install_signal_handlers


class TestInstallSignalHandlers:
    @pytest.mark.asyncio
    async def test_sigterm_sets_event(self):
        event = asyncio.Event()
        install_signal_handlers(event)

        assert not event.is_set()
        os.kill(os.getpid(), signal.SIGTERM)
        # The event loop needs an I/O poll cycle to process the signal
        # self-pipe; sleep(0) only runs scheduled callbacks.
        await asyncio.sleep(0.05)
        assert event.is_set()

    @pytest.mark.asyncio
    async def test_multiple_signals_are_idempotent(self):
        event = asyncio.Event()
        install_signal_handlers(event)

        os.kill(os.getpid(), signal.SIGTERM)
        await asyncio.sleep(0.05)
        assert event.is_set()
        # Second signal should not raise
        os.kill(os.getpid(), signal.SIGTERM)
        await asyncio.sleep(0.05)
        assert event.is_set()

    @pytest.mark.asyncio
    async def test_handlers_registered_for_both_signals(self):
        """Verify handlers are installed for SIGTERM and SIGINT."""
        event = asyncio.Event()
        install_signal_handlers(event)
        loop = asyncio.get_running_loop()

        # asyncio doesn't expose a way to list signal handlers, but we
        # can remove them and confirm they existed (remove returns None
        # only if a handler was previously registered by add_signal_handler).
        result = loop.remove_signal_handler(signal.SIGTERM)
        assert result is True
        result = loop.remove_signal_handler(signal.SIGINT)
        assert result is True
