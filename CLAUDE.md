# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Umbrella is a regulatory communications monitoring platform. It captures messages from multiple channels (email, Teams, Bloomberg, turrets), normalizes them into a canonical schema, and indexes them in Elasticsearch.

## Pipeline Architecture

```
Connectors → Kafka(raw-messages) → Processors → Kafka(parsed-messages)
    → IngestionService → Kafka(normalized-messages) → Logstash → Elasticsearch
```

**Three-stage message flow:**
1. **Connectors** (e.g. `EmailConnector`) poll external systems, store large payloads in S3 (claim-check pattern), publish `RawMessage` to Kafka `raw-messages`
2. **Processors** (e.g. `EmailProcessor`) consume `raw-messages`, download from S3, parse, publish structured data to `parsed-messages`
3. **IngestionService** consumes `parsed-messages`, runs channel-specific normalizers to produce `NormalizedMessage`, dual-writes to Kafka `normalized-messages` + S3

The connector framework (`BaseConnector`) orchestrates Kafka producer, health server, dead-letter handler, and retry logic via `asyncio.TaskGroup`. Connectors implement `ingest()` as an async generator yielding `RawMessage`.

## Key Packages

| Package | Location | Installs as |
|---|---|---|
| Connector framework + shared schema | `connectors/connector-framework/` | `umbrella-connector-framework` (provides `umbrella_connector` + `umbrella_schema`) |
| Email connector | `connectors/email/` | `umbrella-email-connector` (provides `umbrella_email`) |
| Ingestion service | `ingestion-api/` | `umbrella-ingestion` (provides `umbrella_ingestion`) |

All use Hatchling build backend. The email connector and ingestion service both depend on `umbrella-connector-framework` as a local dependency.

## Development Setup

```bash
# Install all packages in editable mode (from repo root, using the existing .venv)
pip install -e connectors/connector-framework/ -e connectors/email/ -e ingestion-api/
```

## Running Tests

```bash
# All tests for a package
pytest connectors/connector-framework/tests/ -v
pytest connectors/email/tests/ -v
pytest ingestion-api/tests/ -v

# Single test file
pytest connectors/connector-framework/tests/test_base.py -v

# Single test
pytest connectors/connector-framework/tests/test_base.py::TestDeliver::test_deliver_success -v
```

All packages use `asyncio_mode = "auto"` — async test functions are detected automatically without needing `@pytest.mark.asyncio` (though existing tests include it).

## Running Services

```bash
# Email connector (Stage 1: IMAP → S3 + Kafka)
python -m umbrella_email connector

# Email processor (Stage 2: Kafka → parse → Kafka)
python -m umbrella_email processor

# Ingestion service (normalize parsed → Kafka + S3)
python -m umbrella_ingestion
```

## Local Infrastructure

```bash
# Kafka (KRaft single-node)
cd infrastructure/kafka && docker compose up -d

# Elasticsearch + Logstash
cd infrastructure/elasticsearch && docker compose up -d
```

## Configuration

All services use **pydantic-settings** with env var prefixes. Key prefixes:
- `KAFKA_` — bootstrap servers, topics, producer settings
- `CONNECTOR_` — connector name, health port
- `RETRY_` — max attempts, backoff settings
- `INGESTION_API_` — base URL, timeout, mTLS paths
- `PROCESSOR_` — processor-specific Kafka and S3 settings
- `S3_` / `AWS_` — S3 endpoint, bucket, credentials

## Kubernetes Deployment

Manifests live in `deploy/k8s/` organized by namespace:
- `umbrella-streaming/` — Kafka StatefulSet + topic-creation Job
- `umbrella-storage/` — Elasticsearch, Logstash, MinIO
- `umbrella-connectors/` — Email processor and future connectors
- `umbrella-ingestion/` — Ingestion/normalization service

Kafka topics: `raw-messages`, `parsed-messages`, `normalized-messages`, `processing-results`, `alerts`, `dead-letter`, `normalized-messages-dlq`

## Conventions

- **Structured logging** via `structlog` everywhere — use `structlog.get_logger()`, log with key-value pairs
- **Pydantic v2** models for all data structures; `model_dump_json()` for serialization
- **Async throughout** — all I/O uses async/await; connectors use `asyncio.run(connector.run())`
- **Normalizer registry pattern** — `ingestion-api/umbrella_ingestion/normalizers/` has a `BaseNormalizer` ABC and `NormalizerRegistry` mapping `Channel` → normalizer
- New connectors: subclass `BaseConnector`, implement `ingest() -> AsyncIterator[RawMessage]`
- New normalizers: subclass `BaseNormalizer`, register in the `NormalizerRegistry`
