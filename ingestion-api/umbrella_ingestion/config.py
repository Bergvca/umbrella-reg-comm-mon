"""Ingestion service configuration loaded from environment variables."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class KafkaConsumerConfig(BaseSettings):
    """Kafka consumer/producer settings for the ingestion service."""

    model_config = {"env_prefix": "KAFKA_"}

    bootstrap_servers: str = Field(
        default="localhost:9092",
        description="Kafka bootstrap servers",
    )
    source_topic: str = Field(
        default="parsed-messages",
        description="Kafka topic to consume parsed messages from",
    )
    output_topic: str = Field(
        default="normalized-messages",
        description="Kafka topic to publish normalized messages to",
    )
    consumer_group: str = Field(
        default="ingestion-normalizer",
        description="Kafka consumer group ID",
    )
    dead_letter_topic: str = Field(
        default="normalized-messages-dlq",
        description="Dead letter topic for failed messages",
    )
    producer_acks: str = Field(
        default="all",
        description="Kafka producer acks setting",
    )
    producer_compression: str = Field(
        default="gzip",
        description="Kafka producer compression type",
    )


class S3Config(BaseSettings):
    """S3 storage settings for normalized message persistence."""

    model_config = {"env_prefix": "S3_"}

    bucket: str = Field(description="S3 bucket name")
    prefix: str = Field(
        default="normalized",
        description="S3 key prefix for normalized messages",
    )
    region: str = Field(default="us-east-1", description="AWS region")
    endpoint_url: str | None = Field(
        default=None,
        description="Custom S3 endpoint URL (e.g. for MinIO)",
    )


class IngestionConfig(BaseSettings):
    """Top-level ingestion service configuration."""

    model_config = {"env_prefix": "INGESTION_"}

    health_port: int = Field(
        default=8082,
        description="Port for K8s health probe endpoints",
    )
    api_port: int = Field(
        default=8000,
        description="Port for optional API server (0 to disable)",
    )
    monitored_domains: list[str] = Field(
        default_factory=list,
        description="Email domains owned by the organization (for direction detection)",
    )
    kafka: KafkaConsumerConfig = Field(default_factory=KafkaConsumerConfig)
    s3: S3Config = Field(default_factory=S3Config)
