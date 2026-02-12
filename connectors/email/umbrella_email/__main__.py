"""Entry point for the email connector package.

Usage::

    python -m umbrella_email connector   # Stage 1: IMAP → S3 + Kafka
    python -m umbrella_email processor   # Stage 2: Kafka → parse → S3 + Kafka
"""

from __future__ import annotations

import asyncio
import sys


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in ("connector", "processor"):
        print("Usage: python -m umbrella_email <connector|processor>", file=sys.stderr)
        sys.exit(1)

    mode = sys.argv[1]

    if mode == "connector":
        from .config import EmailConnectorConfig
        from .connector import EmailConnector

        config = EmailConnectorConfig(name="email")
        connector = EmailConnector(config)
        asyncio.run(connector.run())

    elif mode == "processor":
        from .config import EmailProcessorConfig
        from .processor import EmailProcessor

        config = EmailProcessorConfig()
        processor = EmailProcessor(config)
        asyncio.run(processor.run())


if __name__ == "__main__":
    main()
