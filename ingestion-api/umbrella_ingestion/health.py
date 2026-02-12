"""Health check endpoints for the ingestion service."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.responses import JSONResponse

if TYPE_CHECKING:
    from .service import IngestionService


def create_health_app(service: IngestionService) -> FastAPI:
    """Create a FastAPI app with health and readiness probes."""
    app = FastAPI(title="ingestion-service health", docs_url=None, redoc_url=None)

    @app.get("/health")
    async def health() -> JSONResponse:
        return JSONResponse({
            "service": "ingestion-service",
            "messages_processed": service.messages_processed,
            "messages_skipped": service.messages_skipped,
            "messages_failed": service.messages_failed,
            "supported_channels": service.supported_channels,
        })

    @app.get("/ready")
    async def ready() -> JSONResponse:
        is_ready = service.is_ready
        return JSONResponse(
            {"ready": is_ready},
            status_code=200 if is_ready else 503,
        )

    return app
