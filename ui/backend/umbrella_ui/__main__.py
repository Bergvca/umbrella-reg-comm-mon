"""Entry point: ``python -m umbrella_ui``."""

from __future__ import annotations

import uvicorn

from umbrella_connector import setup_logging

from .config import Settings


def main() -> None:
    settings = Settings()  # type: ignore[call-arg]
    setup_logging(json=settings.log_json, level=settings.log_level)

    uvicorn.run(
        "umbrella_ui.app:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
