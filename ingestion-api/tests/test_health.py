"""Tests for umbrella_ingestion.health."""

from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock

import pytest
from fastapi.testclient import TestClient

from umbrella_ingestion.health import create_health_app


def _make_mock_service(*, is_ready: bool = True) -> MagicMock:
    service = MagicMock()
    service.messages_processed = 42
    service.messages_skipped = 3
    service.messages_failed = 1
    service.supported_channels = ["email"]
    type(service).is_ready = PropertyMock(return_value=is_ready)
    return service


class TestHealthEndpoint:
    def test_health_returns_metrics(self):
        service = _make_mock_service()
        app = create_health_app(service)
        client = TestClient(app)

        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["service"] == "ingestion-service"
        assert data["messages_processed"] == 42
        assert data["messages_skipped"] == 3
        assert data["messages_failed"] == 1
        assert data["supported_channels"] == ["email"]


class TestReadyEndpoint:
    def test_ready_when_consumer_connected(self):
        service = _make_mock_service(is_ready=True)
        app = create_health_app(service)
        client = TestClient(app)

        resp = client.get("/ready")
        assert resp.status_code == 200
        assert resp.json()["ready"] is True

    def test_not_ready_when_consumer_not_connected(self):
        service = _make_mock_service(is_ready=False)
        app = create_health_app(service)
        client = TestClient(app)

        resp = client.get("/ready")
        assert resp.status_code == 503
        assert resp.json()["ready"] is False
