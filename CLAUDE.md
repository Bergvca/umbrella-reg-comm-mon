# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Umbrella is an AI-powered behavioral analytics platform. It ingests data from diverse sources (email, chat, trade feeds, social media, call recordings, etc.), normalizes it into a unified schema, indexes it in Elasticsearch, and applies AI-powered analysis via configurable LangChain agents. Regulatory communications monitoring is one use case among many (trade surveillance, social media monitoring, call centre analytics, etc.).

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

## AI Analytics Layer

The platform's core differentiator is a two-part analytics layer:

**General analytics pipelines** (run automatically on ingested data):
- **Deduplication** — content fingerprinting and fuzzy matching to collapse duplicates across sources
- **Email threading** — reconstructs conversation threads from headers and heuristics
- **Outlier detection** — statistical/ML flagging of anomalous behavior (volume spikes, off-hours activity, unusual patterns)
- **Entity resolution** — links mentions across sources into unified entity profiles
- **Audio transcription & diarization** — Whisper-based speech-to-text with speaker diarization for calls, voicemails, recordings
- **NLP enrichment** — lexicon matching, NER, sentiment analysis, language detection/translation

**LangChain agent system**:
- **Agent Runtime** — LangChain/LangGraph execution engine that loads agent configs from PostgreSQL, runs them with memory, tool calling, and structured output
- **Tool Catalog** — pre-built tools for ES full-text search, ES aggregations, SQL queries, entity lookups
- **Agent definitions and tools** live in `agents/`
- **Agent Builder UI** — no-code interface lives in the UI layer (`ui/`); configs stored in PostgreSQL, executed by the runtime
- Every agent action is logged for audit traceability

## Key Packages

| Package | Location | Installs as |
|---|---|---|
| Connector framework + shared schema | `connectors/connector-framework/` | `umbrella-connector-framework` (provides `umbrella_connector` + `umbrella_schema`) |
| Email connector | `connectors/email/` | `umbrella-email-connector` (provides `umbrella_email`) |
| Ingestion service | `ingestion-api/` | `umbrella-ingestion` (provides `umbrella_ingestion`) |
| Agent runtime + tools | `agents/` | `umbrella-agents` (LangChain agent runtime and tool definitions) |

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

# Ingestion service (Stage 3: normalize parsed → Kafka + S3)
python -m umbrella_ingestion

# Agent runtime service (executes LangChain agents)
python -m umbrella_agents
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
- `LLM_` — LLM provider (OpenAI, Anthropic, self-hosted, etc.), API keys, model selection
- `AGENTS_` — agent service port, PostgreSQL connection (reads agent configs)

## Kubernetes Deployment

Manifests live in `deploy/k8s/` organized by namespace:
- `umbrella-streaming/` — Kafka StatefulSet + topic-creation Job
- `umbrella-storage/` — Elasticsearch, Logstash, MinIO
- `umbrella-connectors/` — Connector and Processor deployments
- `umbrella-ingestion/` — Ingestion/normalization service
- `umbrella-ui/` — UI Backend + Frontend

Kafka topics: `raw-messages`, `parsed-messages`, `normalized-messages`, `processing-results`, `alerts`, `dead-letter`, `normalized-messages-dlq`

## Database Migrations

Migration files live in `infrastructure/postgresql/migrations/` and follow Flyway naming: `V<n>__<description>.sql`.

**When adding a new migration, you must do two things:**
1. Create the `.sql` file in `infrastructure/postgresql/migrations/`
2. Add the SQL content as a new key in the ConfigMap in `deploy/k8s/umbrella-storage/postgresql/migration-job.yaml`

The K8s migration Job (Flyway) reads migrations from a ConfigMap volume — it does not read from the filesystem. The ConfigMap is the source of truth for what runs in the cluster.

## Conventions

- **Structured logging** via `structlog` everywhere — use `structlog.get_logger()`, log with key-value pairs
- **Pydantic v2** models for all data structures; `model_dump_json()` for serialization
- **Async throughout** — all I/O uses async/await; connectors use `asyncio.run(connector.run())`
- **Normalizer registry pattern** — `ingestion-api/umbrella_ingestion/normalizers/` has a `BaseNormalizer` ABC and `NormalizerRegistry` mapping `Channel` → normalizer
- New connectors: subclass `BaseConnector`, implement `ingest() -> AsyncIterator[RawMessage]`
- New normalizers: subclass `BaseNormalizer`, register in the `NormalizerRegistry`
- **LangChain agents** — use LangChain/LangGraph for all AI agent implementations; agents access data via tools (ES and Postgres), not direct DB calls
- use UV for all venv python tasks
