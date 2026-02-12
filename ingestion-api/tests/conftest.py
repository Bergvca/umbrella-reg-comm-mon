"""Shared test fixtures for the ingestion service test suite."""

from __future__ import annotations

import pytest

from umbrella_ingestion.config import IngestionConfig, KafkaConsumerConfig, S3Config


@pytest.fixture
def s3_config() -> S3Config:
    return S3Config(bucket="test-bucket", prefix="normalized", region="us-east-1")


@pytest.fixture
def kafka_config() -> KafkaConsumerConfig:
    return KafkaConsumerConfig(
        bootstrap_servers="localhost:9092",
        source_topic="parsed-messages",
        output_topic="normalized-messages",
        consumer_group="ingestion-test",
    )


@pytest.fixture
def ingestion_config(kafka_config: KafkaConsumerConfig, s3_config: S3Config) -> IngestionConfig:
    return IngestionConfig(
        health_port=18082,
        monitored_domains=["acme.com", "acme.co.uk"],
        kafka=kafka_config,
        s3=s3_config,
    )


# ------------------------------------------------------------------
# Sample parsed email message (EmailProcessor output)
# ------------------------------------------------------------------


def make_parsed_email(
    *,
    raw_message_id: str = "raw-001",
    message_id: str = "<abc@example.com>",
    subject: str = "Test Subject",
    from_address: str = "sender@example.com",
    to: list[str] | None = None,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    date: str = "Mon, 01 Jun 2025 12:00:00 +0000",
    body_text: str = "Hello, World!",
    body_html: str = "<p>Hello</p>",
    attachment_refs: list[str] | None = None,
    raw_eml_s3_uri: str = "s3://bucket/raw/email/100.eml",
) -> dict:
    """Build a parsed email dict matching EmailProcessor output format."""
    return {
        "raw_message_id": raw_message_id,
        "channel": "email",
        "message_id": message_id,
        "subject": subject,
        "from": from_address,
        "to": to or ["recipient@example.com"],
        "cc": cc or [],
        "bcc": bcc or [],
        "date": date,
        "body_text": body_text,
        "body_html": body_html,
        "headers": {"X-Mailer": "TestMailer"},
        "attachment_refs": attachment_refs or [],
        "raw_eml_s3_uri": raw_eml_s3_uri,
    }
