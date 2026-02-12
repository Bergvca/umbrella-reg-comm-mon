"""Tests for umbrella_email.config."""

from __future__ import annotations

from pydantic import SecretStr

from umbrella_email.config import (
    EmailConnectorConfig,
    EmailProcessorConfig,
    ImapConfig,
    S3Config,
)


class TestImapConfig:
    def test_defaults(self):
        cfg = ImapConfig(host="imap.test.com", username="u", password="p")
        assert cfg.port == 993
        assert cfg.use_ssl is True
        assert cfg.mailbox == "INBOX"
        assert cfg.poll_interval_seconds == 30.0

    def test_override(self):
        cfg = ImapConfig(
            host="imap.corp.com",
            port=143,
            use_ssl=False,
            username="admin",
            password="secret",
            mailbox="Journal",
            poll_interval_seconds=10.0,
        )
        assert cfg.port == 143
        assert cfg.use_ssl is False
        assert cfg.mailbox == "Journal"

    def test_password_is_secret(self):
        cfg = ImapConfig(host="h", username="u", password="hunter2")
        assert isinstance(cfg.password, SecretStr)
        assert "hunter2" not in repr(cfg)
        assert cfg.password.get_secret_value() == "hunter2"

    def test_from_env(self, monkeypatch):
        monkeypatch.setenv("IMAP_HOST", "env-imap.example.com")
        monkeypatch.setenv("IMAP_PORT", "143")
        monkeypatch.setenv("IMAP_USERNAME", "envuser")
        monkeypatch.setenv("IMAP_PASSWORD", "envpass")
        monkeypatch.setenv("IMAP_MAILBOX", "Archive")
        cfg = ImapConfig()
        assert cfg.host == "env-imap.example.com"
        assert cfg.port == 143
        assert cfg.mailbox == "Archive"


class TestS3Config:
    def test_defaults(self):
        cfg = S3Config(bucket="my-bucket")
        assert cfg.prefix == "raw/email"
        assert cfg.attachments_prefix == "raw/email/attachments"
        assert cfg.region == "us-east-1"
        assert cfg.endpoint_url is None

    def test_override(self):
        cfg = S3Config(
            bucket="custom",
            prefix="custom/prefix",
            endpoint_url="http://minio:9000",
        )
        assert cfg.endpoint_url == "http://minio:9000"

    def test_from_env(self, monkeypatch):
        monkeypatch.setenv("S3_BUCKET", "env-bucket")
        monkeypatch.setenv("S3_REGION", "eu-west-1")
        cfg = S3Config()
        assert cfg.bucket == "env-bucket"
        assert cfg.region == "eu-west-1"


class TestEmailConnectorConfig:
    def test_inherits_connector_config(self):
        cfg = EmailConnectorConfig(
            name="email",
            imap=ImapConfig(host="h", username="u", password="p"),
            s3=S3Config(bucket="b"),
        )
        assert cfg.name == "email"
        assert cfg.health_port == 8080
        assert cfg.kafka is not None
        assert cfg.retry is not None
        assert cfg.ingestion_api is not None

    def test_has_imap_and_s3(self):
        cfg = EmailConnectorConfig(
            name="email",
            imap=ImapConfig(host="h", username="u", password="p"),
            s3=S3Config(bucket="b"),
        )
        assert cfg.imap.host == "h"
        assert cfg.s3.bucket == "b"


class TestEmailProcessorConfig:
    def test_defaults(self):
        cfg = EmailProcessorConfig(s3=S3Config(bucket="b"))
        assert cfg.kafka_bootstrap_servers == "localhost:9092"
        assert cfg.source_topic == "raw-messages"
        assert cfg.output_topic == "parsed-messages"
        assert cfg.consumer_group == "email-processor"
        assert cfg.health_port == 8081

    def test_from_env(self, monkeypatch):
        monkeypatch.setenv("PROCESSOR_KAFKA_BOOTSTRAP_SERVERS", "broker:9092")
        monkeypatch.setenv("PROCESSOR_OUTPUT_TOPIC", "custom-parsed")
        monkeypatch.setenv("S3_BUCKET", "env-bucket")
        cfg = EmailProcessorConfig()
        assert cfg.kafka_bootstrap_servers == "broker:9092"
        assert cfg.output_topic == "custom-parsed"
