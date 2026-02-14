"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from umbrella_ui.config import Settings
from umbrella_ui.db.engine import DatabaseEngines
from umbrella_ui.es.client import ESClient

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: create DB engines + ES client. Shutdown: dispose."""
    settings: Settings = app.state.settings
    db = DatabaseEngines(settings)
    app.state.db = db
    es = ESClient(settings)
    app.state.es = es
    logger.info("database_engines_created")
    logger.info("elasticsearch_client_created")
    yield
    await es.close()
    await db.close()
    logger.info("shutdown_complete")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and return the FastAPI application."""
    if settings is None:
        settings = Settings()  # type: ignore[call-arg]

    app = FastAPI(
        title="Umbrella UI Backend",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.settings = settings

    from umbrella_ui.routers.alerts import router as alerts_router
    from umbrella_ui.routers.audit import router as audit_router
    from umbrella_ui.routers.auth import router as auth_router
    from umbrella_ui.routers.decisions import router as decisions_router
    from umbrella_ui.routers.export import router as export_router
    from umbrella_ui.routers.groups import router as groups_router
    from umbrella_ui.routers.messages import router as messages_router
    from umbrella_ui.routers.policies import router as policies_router
    from umbrella_ui.routers.policies import rules_router
    from umbrella_ui.routers.queues import router as queues_router
    from umbrella_ui.routers.risk_models import router as risk_models_router
    from umbrella_ui.routers.roles import router as roles_router
    from umbrella_ui.routers.users import router as users_router

    app.include_router(auth_router)
    app.include_router(users_router)
    app.include_router(groups_router)
    app.include_router(roles_router)
    app.include_router(alerts_router)
    app.include_router(messages_router)
    app.include_router(decisions_router)
    app.include_router(queues_router)
    app.include_router(audit_router)
    app.include_router(risk_models_router)
    app.include_router(policies_router)
    app.include_router(rules_router)
    app.include_router(export_router)

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "umbrella-ui-backend"}

    return app
