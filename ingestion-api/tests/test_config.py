"""Tests for umbrella_ingestion.config."""

from __future__ import annotations

from umbrella_ingestion.config import IngestionConfig, KafkaConsumerConfig, S3Config


class TestKafkaConsumerConfig:
    def test_defaults(self):
        cfg = KafkaConsumerConfig()
        assert cfg.bootstrap_servers == "localhost:9092"
        assert cfg.source_topic == "parsed-messages"
        assert cfg.output_topic == "normalized-messages"
        assert cfg.consumer_group == "ingestion-normalizer"
        assert cfg.producer_acks == "all"
        assert cfg.producer_compression == "gzip"

    def test_custom_values(self):
        cfg = KafkaConsumerConfig(
            bootstrap_servers="kafka:29092",
            source_topic="custom-parsed",
            consumer_group="custom-group",
        )
        assert cfg.bootstrap_servers == "kafka:29092"
        assert cfg.source_topic == "custom-parsed"
        assert cfg.consumer_group == "custom-group"


class TestS3Config:
    def test_defaults(self):
        cfg = S3Config(bucket="my-bucket")
        assert cfg.bucket == "my-bucket"
        assert cfg.prefix == "normalized"
        assert cfg.region == "us-east-1"
        assert cfg.endpoint_url is None

    def test_custom_endpoint(self):
        cfg = S3Config(bucket="b", endpoint_url="http://minio:9000")
        assert cfg.endpoint_url == "http://minio:9000"


class TestIngestionConfig:
    def test_defaults(self, ingestion_config: IngestionConfig):
        assert ingestion_config.health_port == 18082
        assert ingestion_config.monitored_domains == ["acme.com", "acme.co.uk"]
        assert ingestion_config.kafka.source_topic == "parsed-messages"
        assert ingestion_config.s3.bucket == "test-bucket"

    def test_api_port_default(self):
        cfg = IngestionConfig(s3=S3Config(bucket="b"))
        assert cfg.api_port == 8000

    def test_empty_monitored_domains(self):
        cfg = IngestionConfig(s3=S3Config(bucket="b"))
        assert cfg.monitored_domains == []
