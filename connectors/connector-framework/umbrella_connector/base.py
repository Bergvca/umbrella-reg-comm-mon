"""BaseConnector — wires up infrastructure and runs the ingest loop."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator

import structlog
import uvicorn

from .config import ConnectorConfig
from .dead_letter import DeadLetterHandler
from .health import create_health_app
from .ingestion_client import IngestionClient
from .interface import ConnectorInterface
from .kafka_producer import KafkaProducerWrapper
from .logging import setup_logging
from .models import ConnectorStatus, RawMessage
from .retry import with_retry
from .shutdown import install_signal_handlers

logger = structlog.get_logger()


class BaseConnector(ConnectorInterface):
    """Base class for all Umbrella connectors.

    Subclasses must implement :meth:`ingest` (and optionally
    :meth:`backfill` and :meth:`health_check`).  Call
    ``asyncio.run(connector.run())`` to start the connector.

    ``run()`` starts the following concurrently via
    :class:`asyncio.TaskGroup`:

    * Kafka producer
    * Ingestion API HTTP client
    * FastAPI health server (for K8s probes)
    * The ingest message loop
    """

    def __init__(self, config: ConnectorConfig) -> None:
        self.config = config
        self.status: ConnectorStatus = ConnectorStatus.STARTING
        self.start_time: float = time.monotonic()

        self._producer = KafkaProducerWrapper(config.kafka)
        self._ingestion_client = IngestionClient(config.ingestion_api)
        self._dead_letter = DeadLetterHandler(self._producer, config.name)
        self._shutdown_event = asyncio.Event()

    # ------------------------------------------------------------------
    # Message delivery with retry + dead-letter
    # ------------------------------------------------------------------

    async def _deliver(self, message: RawMessage) -> None:
        """Deliver a single message to Kafka (required) and ingestion API (best-effort).

        Kafka delivery is retried on failure; if all retries are exhausted, the
        message is sent to the dead-letter queue. HTTP ingestion API delivery is
        best-effort and will not block Kafka delivery.
        """
        # Kafka delivery (required, with retry)
        retry_decorator = with_retry(self.config.retry)

        @retry_decorator
        async def _send_kafka() -> None:
            await self._producer.send_raw(message)

        try:
            await _send_kafka()
        except Exception as exc:
            logger.error(
                "kafka_delivery_failed_permanently",
                raw_message_id=message.raw_message_id,
                error=str(exc),
            )
            await self._dead_letter.send(
                message,
                error=str(exc),
                attempts=self.config.retry.max_attempts,
            )
            return

        # HTTP ingestion API (best-effort, skip if disabled or on failure)
        try:
            await self._ingestion_client.submit(message)
        except Exception as exc:
            logger.warning(
                "ingestion_api_submit_failed",
                raw_message_id=message.raw_message_id,
                error=str(exc),
            )

    # ------------------------------------------------------------------
    # Ingest loop
    # ------------------------------------------------------------------

    async def _run_ingest_loop(self) -> None:
        """Consume messages from ``self.ingest()`` and deliver each one."""
        logger.info("ingest_loop_started", connector=self.config.name)
        self.status = ConnectorStatus.RUNNING

        iterator: AsyncIterator[RawMessage] = self.ingest()
        try:
            async for message in iterator:
                if self._shutdown_event.is_set():
                    break
                await self._deliver(message)
        except Exception:
            self.status = ConnectorStatus.DEGRADED
            logger.exception("ingest_loop_error", connector=self.config.name)
            raise
        finally:
            logger.info("ingest_loop_stopped", connector=self.config.name)

    # ------------------------------------------------------------------
    # Health server
    # ------------------------------------------------------------------

    async def _run_health_server(self) -> None:
        """Start the FastAPI health server and shut it down on signal."""
        app = create_health_app(self)
        config = uvicorn.Config(
            app,
            host="0.0.0.0",
            port=self.config.health_port,
            log_level="warning",
        )
        server = uvicorn.Server(config)

        # Run until the shutdown event fires
        serve_task = asyncio.create_task(server.serve())
        await self._shutdown_event.wait()
        server.should_exit = True
        await serve_task

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    async def run(self) -> None:
        """Start all connector subsystems and run until shutdown.

        This is the single entry point.  Connectors call::

            asyncio.run(connector.run())
        """
        setup_logging()
        install_signal_handlers(self._shutdown_event)
        self.start_time = time.monotonic()

        logger.info("connector_starting", connector=self.config.name)

        await self._producer.start()
        await self._ingestion_client.start()

        try:
            async with asyncio.TaskGroup() as tg:
                tg.create_task(self._run_ingest_loop())
                tg.create_task(self._run_health_server())
        except* Exception:
            logger.exception("connector_task_group_error", connector=self.config.name)
        finally:
            self.status = ConnectorStatus.STOPPING
            await self._ingestion_client.stop()
            await self._producer.stop()
            self.status = ConnectorStatus.STOPPED
            logger.info("connector_stopped", connector=self.config.name)
