"""Entry point for the ingestion service."""

from __future__ import annotations

import asyncio

from umbrella_connector import setup_logging

from .config import IngestionConfig
from .service import IngestionService


def main() -> None:
    setup_logging()
    config = IngestionConfig()
    service = IngestionService(config)
    asyncio.run(service.run())


if __name__ == "__main__":
    main()
