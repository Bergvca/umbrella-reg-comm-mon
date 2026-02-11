"""Umbrella Connector Plugin Framework.

Public API re-exported here for convenience::

    from umbrella_connector import BaseConnector, ConnectorInterface, RawMessage
"""

from .base import BaseConnector
from .config import ConnectorConfig, IngestionAPIConfig, KafkaConfig, RetryConfig
from .dead_letter import DeadLetterHandler
from .health import create_health_app
from .ingestion_client import IngestionClient
from .interface import ConnectorInterface
from .kafka_producer import KafkaProducerWrapper
from .logging import setup_logging
from .models import (
    BackfillRequest,
    ConnectorStatus,
    DeadLetterEnvelope,
    HealthStatus,
    RawMessage,
)
from .retry import with_retry
from .shutdown import install_signal_handlers

__all__ = [
    "BackfillRequest",
    "BaseConnector",
    "ConnectorConfig",
    "ConnectorInterface",
    "ConnectorStatus",
    "DeadLetterEnvelope",
    "DeadLetterHandler",
    "HealthStatus",
    "IngestionAPIConfig",
    "IngestionClient",
    "KafkaConfig",
    "KafkaProducerWrapper",
    "RawMessage",
    "RetryConfig",
    "create_health_app",
    "install_signal_handlers",
    "setup_logging",
    "with_retry",
]
