"""Email connector configuration loaded from environment variables."""

from __future__ import annotations

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings

from umbrella_connector import ConnectorConfig


class ImapConfig(BaseSettings):
    """IMAP server connection settings."""

    model_config = {"env_prefix": "IMAP_"}

    host: str = Field(description="IMAP server hostname")
    port: int = Field(default=993, description="IMAP server port")
    use_ssl: bool = Field(default=True, description="Use SSL/TLS connection")
    username: str = Field(description="IMAP login username")
    password: SecretStr = Field(description="IMAP login password")
    mailbox: str = Field(default="INBOX", description="IMAP mailbox/folder to poll")
    poll_interval_seconds: float = Field(
        default=30.0,
        description="Seconds between IMAP poll cycles",
    )


class S3Config(BaseSettings):
    """S3 storage settings for raw EML and attachments."""

    model_config = {"env_prefix": "S3_"}

    bucket: str = Field(description="S3 bucket name")
    prefix: str = Field(
        default="raw/email",
        description="S3 key prefix for raw EML uploads",
    )
    attachments_prefix: str = Field(
        default="raw/email/attachments",
        description="S3 key prefix for parsed attachment uploads",
    )
    region: str = Field(default="us-east-1", description="AWS region")
    endpoint_url: str | None = Field(
        default=None,
        description="Custom S3 endpoint URL (e.g. for MinIO)",
    )


class EmailConnectorConfig(ConnectorConfig):
    """Stage 1 config: IMAP polling → S3 + Kafka reference.

    Extends ConnectorConfig (inherits kafka, retry, ingestion_api, health_port).
    """

    imap: ImapConfig = Field(default_factory=ImapConfig)
    s3: S3Config = Field(default_factory=S3Config)


class EmailProcessorConfig(BaseSettings):
    """Stage 2 config: Kafka consumer → parse → S3 attachments → Kafka output."""

    model_config = {"env_prefix": "PROCESSOR_"}

    kafka_bootstrap_servers: str = Field(
        default="localhost:9092",
        description="Kafka bootstrap servers",
    )
    source_topic: str = Field(
        default="raw-messages",
        description="Kafka topic to consume raw messages from",
    )
    output_topic: str = Field(
        default="parsed-messages",
        description="Kafka topic to publish parsed messages to",
    )
    consumer_group: str = Field(
        default="email-processor",
        description="Kafka consumer group ID",
    )
    health_port: int = Field(
        default=8081,
        description="Port for K8s health probe endpoints",
    )
    s3: S3Config = Field(default_factory=S3Config)
