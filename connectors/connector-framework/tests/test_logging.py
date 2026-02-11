"""Tests for umbrella_connector.logging."""

from __future__ import annotations

import logging

import structlog

from umbrella_connector.logging import setup_logging


class TestSetupLogging:
    def test_json_mode(self):
        setup_logging(json=True, level="INFO")
        root = logging.getLogger()
        assert root.level == logging.INFO
        assert len(root.handlers) == 1

    def test_console_mode(self):
        setup_logging(json=False, level="DEBUG")
        root = logging.getLogger()
        assert root.level == logging.DEBUG

    def test_level_case_insensitive(self):
        setup_logging(level="warning")
        root = logging.getLogger()
        assert root.level == logging.WARNING

    def test_replaces_existing_handlers(self):
        root = logging.getLogger()
        root.addHandler(logging.StreamHandler())
        root.addHandler(logging.StreamHandler())
        assert len(root.handlers) >= 2
        setup_logging()
        assert len(root.handlers) == 1

    def test_structlog_produces_output(self):
        setup_logging(json=True, level="DEBUG")
        logger = structlog.get_logger("test_logger")
        # Should not raise — verifies the full pipeline is wired up
        logger.info("test_event", key="value")
