"""Tests for umbrella_connector.config."""

from __future__ import annotations

from umbrella_connector.config import (
    ConnectorConfig,
    IngestionAPIConfig,
    KafkaConfig,
    RetryConfig,
)


class TestKafkaConfig:
    def test_defaults(self):
        cfg = KafkaConfig()
        assert cfg.bootstrap_servers == "localhost:9092"
        assert cfg.raw_messages_topic == "raw-messages"
        assert cfg.dead_letter_topic == "dead-letter"
        assert cfg.producer_acks == "all"
        assert cfg.producer_compression == "gzip"

    def test_override(self):
        cfg = KafkaConfig(
            bootstrap_servers="broker1:9092,broker2:9092",
            raw_messages_topic="custom-raw",
        )
        assert cfg.bootstrap_servers == "broker1:9092,broker2:9092"
        assert cfg.raw_messages_topic == "custom-raw"

    def test_from_env(self, monkeypatch):
        monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "envbroker:9092")
        monkeypatch.setenv("KAFKA_DEAD_LETTER_TOPIC", "env-dlq")
        cfg = KafkaConfig()
        assert cfg.bootstrap_servers == "envbroker:9092"
        assert cfg.dead_letter_topic == "env-dlq"


class TestRetryConfig:
    def test_defaults(self):
        cfg = RetryConfig()
        assert cfg.max_attempts == 5
        assert cfg.initial_wait_seconds == 1.0
        assert cfg.max_wait_seconds == 60.0
        assert cfg.multiplier == 2.0

    def test_override(self):
        cfg = RetryConfig(max_attempts=10, multiplier=3.0)
        assert cfg.max_attempts == 10
        assert cfg.multiplier == 3.0

    def test_from_env(self, monkeypatch):
        monkeypatch.setenv("RETRY_MAX_ATTEMPTS", "7")
        monkeypatch.setenv("RETRY_INITIAL_WAIT_SECONDS", "0.5")
        cfg = RetryConfig()
        assert cfg.max_attempts == 7
        assert cfg.initial_wait_seconds == 0.5


class TestIngestionAPIConfig:
    def test_defaults(self):
        cfg = IngestionAPIConfig()
        assert cfg.base_url == ""  # empty by default (disabled)
        assert cfg.timeout_seconds == 30.0
        assert cfg.mtls_cert_path is None
        assert cfg.mtls_key_path is None
        assert cfg.mtls_ca_path is None

    def test_mtls_paths(self):
        cfg = IngestionAPIConfig(
            mtls_cert_path="/certs/client.crt",
            mtls_key_path="/certs/client.key",
            mtls_ca_path="/certs/ca.crt",
        )
        assert cfg.mtls_cert_path == "/certs/client.crt"

    def test_from_env(self, monkeypatch):
        monkeypatch.setenv("INGESTION_API_BASE_URL", "https://api.prod:443")
        monkeypatch.setenv("INGESTION_API_TIMEOUT_SECONDS", "60")
        cfg = IngestionAPIConfig()
        assert cfg.base_url == "https://api.prod:443"
        assert cfg.timeout_seconds == 60.0


class TestConnectorConfig:
    def test_construction_with_name(self):
        cfg = ConnectorConfig(name="teams-chat")
        assert cfg.name == "teams-chat"
        assert cfg.health_port == 8080
        assert isinstance(cfg.kafka, KafkaConfig)
        assert isinstance(cfg.retry, RetryConfig)
        assert isinstance(cfg.ingestion_api, IngestionAPIConfig)

    def test_nested_overrides(self):
        cfg = ConnectorConfig(
            name="email",
            health_port=9090,
            kafka=KafkaConfig(bootstrap_servers="custom:9092"),
            retry=RetryConfig(max_attempts=10),
        )
        assert cfg.kafka.bootstrap_servers == "custom:9092"
        assert cfg.retry.max_attempts == 10

    def test_from_env(self, monkeypatch):
        monkeypatch.setenv("CONNECTOR_NAME", "env-connector")
        monkeypatch.setenv("CONNECTOR_HEALTH_PORT", "9999")
        cfg = ConnectorConfig()
        assert cfg.name == "env-connector"
        assert cfg.health_port == 9999
