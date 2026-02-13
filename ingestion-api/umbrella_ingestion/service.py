"""IngestionService — consume parsed messages, normalize, dual-write to Kafka + S3."""

from __future__ import annotations

import asyncio
import json
import signal
import time

import structlog
import uvicorn
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

from .config import IngestionConfig
from .health import create_health_app
from .normalizers.email import EmailNormalizer
from .normalizers.registry import NormalizerRegistry
from .s3 import NormalizedS3Store

logger = structlog.get_logger()


class IngestionService:
    """Consume parsed messages, normalize via registry, dual-write to Kafka + S3."""

    def __init__(self, config: IngestionConfig) -> None:
        self._config = config
        self._s3 = NormalizedS3Store(config.s3)
        self._registry = NormalizerRegistry()
        self._registry.register(EmailNormalizer(config.monitored_domains))

        self._consumer: AIOKafkaConsumer | None = None
        self._producer: AIOKafkaProducer | None = None
        self._shutdown_event = asyncio.Event()

        self._messages_processed: int = 0
        self._messages_skipped: int = 0
        self._messages_failed: int = 0
        self._start_time: float = 0.0

    # ------------------------------------------------------------------
    # Public properties (used by health checks)
    # ------------------------------------------------------------------

    @property
    def messages_processed(self) -> int:
        return self._messages_processed

    @property
    def messages_skipped(self) -> int:
        return self._messages_skipped

    @property
    def messages_failed(self) -> int:
        return self._messages_failed

    @property
    def supported_channels(self) -> list[str]:
        return self._registry.supported_channels

    @property
    def is_ready(self) -> bool:
        return self._consumer is not None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def run(self) -> None:
        """Start all subsystems and process messages until shutdown."""
        self._start_time = time.monotonic()
        self._install_signal_handlers()

        kafka_cfg = self._config.kafka

        self._consumer = AIOKafkaConsumer(
            kafka_cfg.source_topic,
            bootstrap_servers=kafka_cfg.bootstrap_servers,
            group_id=kafka_cfg.consumer_group,
            auto_offset_reset=kafka_cfg.auto_offset_reset,
            enable_auto_commit=False,
        )
        self._producer = AIOKafkaProducer(
            bootstrap_servers=kafka_cfg.bootstrap_servers,
            acks=kafka_cfg.producer_acks,
            compression_type=kafka_cfg.producer_compression,
        )

        await self._s3.start()
        await self._consumer.start()
        await self._producer.start()
        logger.info("ingestion_service_started")

        try:
            async with asyncio.TaskGroup() as tg:
                tg.create_task(self._consume_loop())
                tg.create_task(self._run_health_server())
        except* Exception:
            logger.exception("ingestion_service_error")
        finally:
            await self._producer.stop()
            await self._consumer.stop()
            await self._s3.stop()
            logger.info("ingestion_service_stopped")

    # ------------------------------------------------------------------
    # Consume loop
    # ------------------------------------------------------------------

    async def _consume_loop(self) -> None:
        assert self._consumer is not None
        assert self._producer is not None

        async for msg in self._consumer:
            if self._shutdown_event.is_set():
                break

            try:
                raw_message = json.loads(msg.value.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                logger.exception("message_deserialize_failed", offset=msg.offset)
                self._messages_failed += 1
                await self._consumer.commit()
                continue

            channel = raw_message.get("channel")

            normalizer = self._registry.get(channel)
            if normalizer is None:
                logger.warning("no_normalizer", channel=channel)
                self._messages_skipped += 1
                await self._consumer.commit()
                continue

            try:
                normalized = normalizer.normalize(raw_message)
                await self._dual_write(normalized)
                self._messages_processed += 1
                await self._consumer.commit()
            except Exception:
                logger.exception(
                    "normalization_failed",
                    channel=channel,
                    message_id=raw_message.get("message_id"),
                )
                self._messages_failed += 1
                # Commit to avoid poison-pill blocking
                await self._consumer.commit()

    # ------------------------------------------------------------------
    # Dual write
    # ------------------------------------------------------------------

    async def _dual_write(self, normalized) -> None:
        assert self._producer is not None

        # 1. Kafka
        value = normalized.model_dump_json().encode("utf-8")
        key = normalized.message_id.encode("utf-8")
        await self._producer.send_and_wait(
            self._config.kafka.output_topic,
            value=value,
            key=key,
        )

        # 2. S3
        s3_uri = await self._s3.store(normalized)

        logger.info(
            "message_normalized",
            message_id=normalized.message_id,
            channel=normalized.channel.value,
            direction=normalized.direction.value,
            s3_uri=s3_uri,
        )

    # ------------------------------------------------------------------
    # Health server
    # ------------------------------------------------------------------

    async def _run_health_server(self) -> None:
        app = create_health_app(self)
        config = uvicorn.Config(
            app,
            host="0.0.0.0",
            port=self._config.health_port,
            log_level="warning",
        )
        server = uvicorn.Server(config)

        serve_task = asyncio.create_task(server.serve())
        await self._shutdown_event.wait()
        server.should_exit = True
        await serve_task

    # ------------------------------------------------------------------
    # Signal handling
    # ------------------------------------------------------------------

    def _install_signal_handlers(self) -> None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._shutdown_event.set)
