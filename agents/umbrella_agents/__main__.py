"""Entry point: ``python -m umbrella_agents``."""

from __future__ import annotations

import structlog
import uvicorn

from .config import Settings


def main() -> None:
    settings = Settings()  # type: ignore[call-arg]
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
            if settings.log_json
            else structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.PrintLoggerFactory(),
    )

    uvicorn.run(
        "umbrella_agents.app:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
