"""Typed async Kafka producer wrapper."""

from __future__ import annotations

from aiokafka import AIOKafkaProducer
import structlog

from .config import KafkaConfig
from .models import DeadLetterEnvelope, RawMessage

logger = structlog.get_logger()


class KafkaProducerWrapper:
    """Thin async wrapper around :class:`AIOKafkaProducer`.

    Provides typed ``send_raw`` and ``send_dead_letter`` helpers
    that serialize models to JSON and route to the correct topic.
    """

    def __init__(self, config: KafkaConfig) -> None:
        self._config = config
        self._producer: AIOKafkaProducer | None = None

    async def start(self) -> None:
        self._producer = AIOKafkaProducer(
            bootstrap_servers=self._config.bootstrap_servers,
            acks=self._config.producer_acks,
            compression_type=self._config.producer_compression,
            value_serializer=lambda v: v.encode("utf-8") if isinstance(v, str) else v,
        )
        await self._producer.start()
        logger.info("kafka_producer_started", servers=self._config.bootstrap_servers)

    async def stop(self) -> None:
        if self._producer is not None:
            await self._producer.stop()
            logger.info("kafka_producer_stopped")

    async def send_raw(self, message: RawMessage) -> None:
        """Publish a raw message to the raw-messages topic."""
        assert self._producer is not None, "Producer not started"
        value = message.model_dump_json().encode("utf-8")
        await self._producer.send_and_wait(
            self._config.raw_messages_topic,
            value=value,
            key=message.raw_message_id.encode("utf-8"),
        )
        logger.debug(
            "raw_message_sent",
            topic=self._config.raw_messages_topic,
            raw_message_id=message.raw_message_id,
        )

    async def send_dead_letter(self, envelope: DeadLetterEnvelope) -> None:
        """Publish a dead-letter envelope to the dead-letter topic."""
        assert self._producer is not None, "Producer not started"
        value = envelope.model_dump_json().encode("utf-8")
        await self._producer.send_and_wait(
            self._config.dead_letter_topic,
            value=value,
            key=envelope.original_message.raw_message_id.encode("utf-8"),
        )
        logger.warning(
            "dead_letter_sent",
            topic=self._config.dead_letter_topic,
            raw_message_id=envelope.original_message.raw_message_id,
            error=envelope.error,
        )
