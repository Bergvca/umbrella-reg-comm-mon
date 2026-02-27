"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from umbrella_agents.config import Settings
from umbrella_agents.db.engine import AgentEngine
from umbrella_agents.es.client import ESClient
from umbrella_agents.run_registry import RunRegistry

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: create DB engine + ES client. Shutdown: dispose."""
    settings: Settings = app.state.settings
    db = AgentEngine(settings)
    app.state.db = db
    es = ESClient(settings)
    app.state.es = es
    app.state.run_registry = RunRegistry()
    logger.info("agent_engine_created")
    logger.info("elasticsearch_client_created")
    yield
    await app.state.run_registry.cancel_all()
    await es.close()
    await db.close()
    logger.info("shutdown_complete")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and return the FastAPI application."""
    if settings is None:
        settings = Settings()  # type: ignore[call-arg]

    app = FastAPI(
        title="Umbrella Agent Runtime",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.settings = settings

    # Import tool modules to trigger registration with the global registry
    import umbrella_agents.tools.es_get_mapping  # noqa: F401
    import umbrella_agents.tools.es_search  # noqa: F401
    import umbrella_agents.tools.sql_query  # noqa: F401

    from umbrella_agents.routers.execute import router as execute_router
    from umbrella_agents.routers.health import router as health_router
    from umbrella_agents.routers.stream import router as stream_router
    from umbrella_agents.routers.translate import router as translate_router

    app.include_router(health_router)
    app.include_router(translate_router)
    app.include_router(execute_router)
    app.include_router(stream_router)

    return app
