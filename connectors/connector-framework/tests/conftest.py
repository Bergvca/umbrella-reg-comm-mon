"""Shared test fixtures for the umbrella_connector test suite."""

from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock

import pytest

from umbrella_connector.config import (
    ConnectorConfig,
    IngestionAPIConfig,
    KafkaConfig,
    RetryConfig,
)
from umbrella_connector.models import RawMessage
from umbrella_schema import Channel


@pytest.fixture
def kafka_config() -> KafkaConfig:
    return KafkaConfig(
        bootstrap_servers="localhost:9092",
        raw_messages_topic="raw-messages",
        dead_letter_topic="dead-letter",
    )


@pytest.fixture
def retry_config() -> RetryConfig:
    return RetryConfig(
        max_attempts=3,
        initial_wait_seconds=0.01,
        max_wait_seconds=0.1,
        multiplier=2.0,
    )


@pytest.fixture
def ingestion_api_config() -> IngestionAPIConfig:
    return IngestionAPIConfig(base_url="http://test-api:8000")


@pytest.fixture
def connector_config(
    kafka_config: KafkaConfig,
    retry_config: RetryConfig,
    ingestion_api_config: IngestionAPIConfig,
) -> ConnectorConfig:
    return ConnectorConfig(
        name="test-connector",
        health_port=18080,
        kafka=kafka_config,
        retry=retry_config,
        ingestion_api=ingestion_api_config,
    )


@pytest.fixture
def raw_message() -> RawMessage:
    return RawMessage(
        raw_message_id="msg-001",
        channel=Channel.TEAMS_CHAT,
        raw_payload={"text": "hello world"},
        raw_format="json",
        attachment_refs=["s3://bucket/att1.pdf"],
        metadata={"correlation_id": "corr-123"},
    )


@pytest.fixture
def raw_message_factory():
    """Factory to create RawMessage instances with overrides."""

    def _make(**overrides) -> RawMessage:
        defaults = dict(
            raw_message_id="msg-factory",
            channel=Channel.EMAIL,
            raw_payload={"subject": "test"},
        )
        defaults.update(overrides)
        return RawMessage(**defaults)

    return _make


@pytest.fixture
def mock_kafka_producer() -> AsyncMock:
    """A mock AIOKafkaProducer with async start/stop/send_and_wait."""
    producer = AsyncMock()
    producer.start = AsyncMock()
    producer.stop = AsyncMock()
    producer.send_and_wait = AsyncMock()
    return producer
