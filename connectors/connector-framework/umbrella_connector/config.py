"""Connector configuration loaded from environment variables.

Uses pydantic-settings so every field can be overridden via env vars,
which is the natural config mechanism in Kubernetes.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class KafkaConfig(BaseSettings):
    """Kafka connection and topic settings."""

    model_config = {"env_prefix": "KAFKA_"}

    bootstrap_servers: str = Field(
        default="localhost:9092",
        description="Comma-separated Kafka bootstrap servers",
    )
    raw_messages_topic: str = Field(
        default="raw-messages",
        description="Topic for raw messages produced by connectors",
    )
    dead_letter_topic: str = Field(
        default="dead-letter",
        description="Topic for messages that failed delivery after retries",
    )
    producer_acks: str = Field(
        default="all",
        description="Producer acknowledgement level",
    )
    producer_compression: str = Field(
        default="gzip",
        description="Compression codec for produced messages",
    )


class RetryConfig(BaseSettings):
    """Retry / backoff settings driven by Tenacity."""

    model_config = {"env_prefix": "RETRY_"}

    max_attempts: int = Field(default=5, description="Maximum delivery attempts per message")
    initial_wait_seconds: float = Field(
        default=1.0,
        description="Initial backoff wait in seconds",
    )
    max_wait_seconds: float = Field(
        default=60.0,
        description="Maximum backoff wait in seconds",
    )
    multiplier: float = Field(default=2.0, description="Exponential backoff multiplier")


class IngestionAPIConfig(BaseSettings):
    """Ingestion API HTTP client settings."""

    model_config = {"env_prefix": "INGESTION_API_"}

    base_url: str = Field(
        default="http://ingestion-api:8000",
        description="Base URL of the ingestion API",
    )
    timeout_seconds: float = Field(default=30.0, description="HTTP request timeout")
    mtls_cert_path: str | None = Field(
        default=None,
        description="Path to client certificate for mTLS",
    )
    mtls_key_path: str | None = Field(
        default=None,
        description="Path to client private key for mTLS",
    )
    mtls_ca_path: str | None = Field(
        default=None,
        description="Path to CA bundle for mTLS verification",
    )


class ConnectorConfig(BaseSettings):
    """Root configuration for a connector instance.

    Nested configs are populated from their own env-var prefixes.
    """

    model_config = {"env_prefix": "CONNECTOR_"}

    name: str = Field(description="Unique connector name (e.g. teams-chat)")
    health_port: int = Field(default=8080, description="Port for K8s health probe endpoints")

    kafka: KafkaConfig = Field(default_factory=KafkaConfig)
    retry: RetryConfig = Field(default_factory=RetryConfig)
    ingestion_api: IngestionAPIConfig = Field(default_factory=IngestionAPIConfig)
