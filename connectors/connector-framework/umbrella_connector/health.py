"""FastAPI health endpoints for Kubernetes liveness and readiness probes."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .models import ConnectorStatus, HealthStatus

if TYPE_CHECKING:
    from .base import BaseConnector


def create_health_app(connector: BaseConnector) -> FastAPI:
    """Build a minimal FastAPI app with ``/health`` and ``/ready`` routes.

    The *connector* reference is used to read runtime status and
    delegate to the connector's ``health_check()`` method.
    """
    app = FastAPI(title=f"{connector.config.name} health", docs_url=None, redoc_url=None)

    @app.get("/health")
    async def health() -> JSONResponse:
        details = await connector.health_check()
        status = HealthStatus(
            connector_name=connector.config.name,
            status=connector.status,
            uptime_seconds=time.monotonic() - connector.start_time,
            details=details,
        )
        code = 200 if connector.status in (ConnectorStatus.RUNNING, ConnectorStatus.STARTING) else 503
        return JSONResponse(content=status.model_dump(mode="json"), status_code=code)

    @app.get("/ready")
    async def ready() -> JSONResponse:
        is_ready = connector.status == ConnectorStatus.RUNNING
        return JSONResponse(
            content={"ready": is_ready},
            status_code=200 if is_ready else 503,
        )

    return app
