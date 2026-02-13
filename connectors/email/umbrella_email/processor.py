"""Stage 2 — EmailProcessor: consume raw-messages from Kafka, download
raw EML from S3, full MIME parse, upload attachments, publish to
parsed-messages topic.
"""

from __future__ import annotations

import asyncio
import json
import signal
import time

import structlog
import uvicorn
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .config import EmailProcessorConfig
from .parser import MimeParser
from .s3 import S3Store

logger = structlog.get_logger()


class EmailProcessor:
    """Kafka consumer that parses raw EML references into structured messages.

    Consumes ``RawMessage`` envelopes from the ``raw-messages`` topic
    (where ``channel == "email"`` and ``raw_format == "eml_ref"``),
    downloads the raw EML from S3, performs a full MIME parse, uploads
    individual attachments to S3, and publishes the structured result
    to ``parsed-messages``.
    """

    def __init__(self, config: EmailProcessorConfig) -> None:
        self._config = config
        self._s3 = S3Store(config.s3)
        self._parser = MimeParser()
        self._consumer: AIOKafkaConsumer | None = None
        self._producer: AIOKafkaProducer | None = None
        self._shutdown_event = asyncio.Event()
        self._messages_processed: int = 0
        self._start_time: float = 0.0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def run(self) -> None:
        """Start all subsystems and process messages until shutdown."""
        self._start_time = time.monotonic()
        self._install_signal_handlers()

        self._consumer = AIOKafkaConsumer(
            self._config.source_topic,
            bootstrap_servers=self._config.kafka_bootstrap_servers,
            group_id=self._config.consumer_group,
            enable_auto_commit=False,
            auto_offset_reset=self._config.auto_offset_reset,
        )
        self._producer = AIOKafkaProducer(
            bootstrap_servers=self._config.kafka_bootstrap_servers,
            compression_type="gzip",
        )

        await self._s3.start()
        await self._consumer.start()
        await self._producer.start()
        logger.info("email_processor_started")

        try:
            async with asyncio.TaskGroup() as tg:
                tg.create_task(self._consume_loop())
                tg.create_task(self._run_health_server())
        except* Exception:
            logger.exception("email_processor_error")
        finally:
            await self._producer.stop()
            await self._consumer.stop()
            await self._s3.stop()
            logger.info("email_processor_stopped")

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
                logger.warning("email_processor_invalid_json", offset=msg.offset)
                await self._consumer.commit()
                continue
            # Filter: only process email channel with eml_ref format
            if raw_message.get("channel") != "email":
                await self._consumer.commit()
                continue
            if raw_message.get("raw_format") != "eml_ref":
                await self._consumer.commit()
                continue

            try:
                await self._process_message(raw_message)
                await self._consumer.commit()
                self._messages_processed += 1
            except Exception:
                logger.exception(
                    "email_processing_failed",
                    raw_message_id=raw_message.get("raw_message_id"),
                )
                # Commit anyway to avoid poison-pill blocking.
                # The raw EML is safely in S3 and can be reprocessed.
                await self._consumer.commit()

    async def _process_message(self, raw_message: dict) -> None:
        assert self._producer is not None

        s3_uri = raw_message["raw_payload"]["s3_uri"]
        raw_message_id = raw_message["raw_message_id"]

        # Download raw EML from S3
        raw_bytes = await self._s3.download_raw_eml(s3_uri)

        # Full MIME parse
        parsed = self._parser.parse(raw_bytes)

        # Upload individual attachments to S3
        email_uid = raw_message.get("metadata", {}).get("imap_uid", raw_message_id)
        attachment_refs = await self._s3.upload_attachments(
            email_uid,
            parsed.attachments,
        )

        # Build structured output
        parsed_output = {
            "raw_message_id": raw_message_id,
            "channel": "email",
            "message_id": parsed.message_id,
            "subject": parsed.subject,
            "from": parsed.from_address,
            "to": parsed.to_addresses,
            "cc": parsed.cc_addresses,
            "bcc": parsed.bcc_addresses,
            "date": parsed.date,
            "body_text": parsed.body_text,
            "body_html": parsed.body_html,
            "headers": parsed.headers,
            "attachment_refs": attachment_refs,
            "raw_eml_s3_uri": s3_uri,
        }

        # Publish to parsed-messages topic
        value = json.dumps(parsed_output).encode("utf-8")
        await self._producer.send_and_wait(
            self._config.output_topic,
            value=value,
            key=raw_message_id.encode("utf-8"),
        )

        logger.info(
            "email_parsed",
            raw_message_id=raw_message_id,
            attachments=len(attachment_refs),
        )

    # ------------------------------------------------------------------
    # Health server
    # ------------------------------------------------------------------

    async def _run_health_server(self) -> None:
        app = FastAPI(title="email-processor health", docs_url=None, redoc_url=None)

        @app.get("/health")
        async def health() -> JSONResponse:
            return JSONResponse({
                "service": "email-processor",
                "uptime_seconds": time.monotonic() - self._start_time,
                "messages_processed": self._messages_processed,
            })

        @app.get("/ready")
        async def ready() -> JSONResponse:
            is_ready = self._consumer is not None
            return JSONResponse(
                {"ready": is_ready},
                status_code=200 if is_ready else 503,
            )

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
