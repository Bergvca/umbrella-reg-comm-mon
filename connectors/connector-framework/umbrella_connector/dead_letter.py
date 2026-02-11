"""Dead-letter handler — routes failed messages to the dead-letter Kafka topic."""

from __future__ import annotations

import structlog

from .kafka_producer import KafkaProducerWrapper
from .models import DeadLetterEnvelope, RawMessage

logger = structlog.get_logger()


class DeadLetterHandler:
    """Wraps a failed :class:`RawMessage` in a :class:`DeadLetterEnvelope`
    and publishes it to the dead-letter Kafka topic.
    """

    def __init__(self, producer: KafkaProducerWrapper, connector_name: str) -> None:
        self._producer = producer
        self._connector_name = connector_name

    async def send(
        self,
        message: RawMessage,
        *,
        error: str,
        attempts: int,
    ) -> None:
        """Build a dead-letter envelope and publish it."""
        envelope = DeadLetterEnvelope(
            original_message=message,
            connector_name=self._connector_name,
            error=error,
            attempts=attempts,
        )
        await self._producer.send_dead_letter(envelope)
        logger.error(
            "message_dead_lettered",
            raw_message_id=message.raw_message_id,
            connector=self._connector_name,
            error=error,
            attempts=attempts,
        )
