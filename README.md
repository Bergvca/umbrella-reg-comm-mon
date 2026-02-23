# Umbrella — AI-Powered Behavioral Analytics Platform

```
                                  .
                             .    |    .
                          .       |       .
                       .          |          .
                    .─────────────┼─────────────.
                 ──'              |              '──
              ──'    ░░░░░░░░░░░░░░░░░░░░░░░░░    '──
           ──'                   |                   '──
        ──'                      |                      '──
      ─'─────────────────────────┼─────────────────────────'─
                                 │
                                 │
                   ╱  ╱  ╱  ╱   │   ╲  ╲  ╲  ╲
                 ╱  ╱  ╱  ╱     │     ╲  ╲  ╲  ╲
               ╱  ╱  ╱  ╱       │       ╲  ╲  ╲  ╲
             ╱  ╱  ╱  ╱         │         ╲  ╲  ╲  ╲
           ╱  ╱  ╱  ╱    ┌─────┴─────┐     ╲  ╲  ╲  ╲
         ╱  ╱  ╱  ╱      │ PROTECTED │       ╲  ╲  ╲  ╲
       ╱  ╱  ╱  ╱        │   data    │         ╲  ╲  ╲  ╲
     ╱  ╱  ╱  ╱          └───────────┘           ╲  ╲  ╲  ╲
```

## Overview

Umbrella is a **behavioral analytics platform** that ingests data from diverse sources, normalizes it into a unified schema, and applies **AI-powered analysis** to surface insights, anomalies, and alerts. The platform is built around a flexible **agent builder** — powered by LangChain — that lets users create custom AI agents to query Elasticsearch and PostgreSQL, enabling deep analytical workflows without writing code.

While the data ingestion pipeline is domain-agnostic, Umbrella ships with purpose-built use cases including:

- **Regulatory Communications Monitoring** — eComm/aComm capture and compliance review for financial institutions
- **Trade Surveillance** — detecting market abuse, insider trading, and suspicious trading patterns
- **Social Media Monitoring** — tracking brand sentiment, misinformation, and behavioral signals across platforms
- **Call Centre Analytics** — analyzing customer interactions for quality, compliance, and behavioral trends
- **Internal Communications Monitoring** — detecting policy violations, data leakage, and conduct risk

## AI Analytics Layer

The core differentiator is Umbrella's **AI analytics layer**. It combines general-purpose analytics pipelines with LangChain-powered AI agents. It provides:

### General Analytics

Pipelines that run automatically on ingested data:

- **Deduplication** — detects and collapses duplicate messages across sources using content fingerprinting and fuzzy matching
- **Email threading** — reconstructs conversation threads from `In-Reply-To` / `References` headers and subject-line heuristics
- **Outlier detection** — statistical and ML-based flagging of anomalous behavior (volume spikes, unusual communication patterns, off-hours activity)
- **Entity resolution** — links mentions of people, organizations, and accounts across sources into unified entity profiles
- **Audio transcription & diarization** — speech-to-text via Whisper with speaker diarization, producing searchable transcripts from calls, voicemails, and recordings
- **NLP enrichment** — lexicon matching, named entity recognition, sentiment analysis, language detection and translation

### Agent Builder (UI)

The UI includes a no-code/low-code **agent builder** for creating and managing custom AI agents. Users configure agents through the dashboard, and the AI layer executes them. Each agent is configured with:

- **Model** — any LLM backend: cloud APIs (OpenAI, Anthropic, Google, etc.), self-hosted open-source models (Llama, Mistral, etc. via vLLM/Ollama), or private fine-tuned models — swap with a single config change
- **Data sources** — which Elasticsearch indices and/or PostgreSQL tables the agent can query
- **Tools** — pre-built tool catalog (ES full-text search, ES aggregations, SQL queries, entity lookups, time-series analysis) plus custom tool definitions
- **Instructions** — natural language system prompts defining the agent's role, goals, and constraints
- **Output schema** — structured output definitions for alerts, reports, or disposition recommendations

Agent configurations are stored in PostgreSQL and executed by the AI analytics layer at runtime.

### Pre-built Agents

Umbrella ships with ready-to-use agents for common use cases:

| Agent | Description |
|---|---|
| **Comms Reviewer** | Reviews flagged communications, drafts dispositions with cited evidence |
| **Trade Surveillance** | Correlates trade data with communications to detect suspicious patterns |
| **Entity Risk Profiler** | Builds behavioral risk profiles by aggregating activity across data sources |
| **Anomaly Detector** | Identifies statistical outliers and behavioral deviations in time-series data |
| **Semantic Search** | RAG-powered natural language search across all indexed data |

### Agent Capabilities

- **Elasticsearch queries** — full-text search, aggregations, percolator alerts, vector similarity
- **PostgreSQL queries** — structured data lookups, entity resolution, audit trails, policy configurations
- **Cross-source correlation** — join insights from ES and Postgres in a single analytical chain
- **Context enrichment** — agents can call other agents, building rich context packages for human reviewers
- **Audit trail** — every agent action, query, and decision is logged for full traceability

## Pipeline Architecture

All data sources follow the same **three-stage ingestion pipeline**:

```
Data Source (IMAP, API, Stream, File, ...)
    │
    ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  STAGE 1 — CONNECTOR                                                        │
│  Poll/stream the external system. Store large payloads in S3 using the      │
│  claim-check pattern. Publish RawMessage to Kafka `raw-messages`.           │
└──────────┬───────────────────────────────────────────────────────────────────┘
           │  RawMessage → S3 (payload) + Kafka `raw-messages` (pointer)
           ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  STAGE 2 — PROCESSOR                                                        │
│  Consume from `raw-messages`. Download payload from S3. Parse the           │
│  source-specific format into structured data. Publish to Kafka              │
│  `parsed-messages`.                                                          │
└──────────┬───────────────────────────────────────────────────────────────────┘
           │  Structured/parsed data → Kafka `parsed-messages`
           ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  STAGE 3 — INGESTION / NORMALIZATION                                        │
│  Consume from `parsed-messages`. Run the appropriate normalizer             │
│  (via NormalizerRegistry) to produce a NormalizedMessage. Dual-write:       │
│    • NormalizedMessage → Kafka `normalized-messages`                        │
│    • NormalizedMessage → S3 archive                                         │
└──────────┬───────────────────────────────────────────────────────────────────┘
           │  NormalizedMessage → Kafka `normalized-messages` + S3
           ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  LOGSTASH → ELASTICSEARCH                                                    │
│  Logstash consumes `normalized-messages`, transforms, and indexes into ES.  │
└──────────────────────────────────────────────────────────────────────────────┘
```

### System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                         STAGE 1 — CONNECTORS                                        │
│                                                                                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐    │
│  │  Email    │ │  Teams   │ │  Trade   │ │  Social  │ │  Call    │ │  Custom  │    │
│  │  (IMAP)  │ │  Chat    │ │  Feed    │ │  Media   │ │  Centre  │ │  Source  │    │
│  │ Connector│ │ Connector│ │ Connector│ │ Connector│ │ Connector│ │ Connector│    │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘    │
│       └─────────────┴────────────┴──────┬──────┴─────────────┴────────────┘          │
│                              ┌──────────┴──────────┐                                 │
│                              │   BaseConnector      │   Shared framework:             │
│                              │   Framework          │   Kafka, S3, health,            │
│                              │                      │   DLQ, retry, TaskGroup         │
│                              └──────────┬───────────┘                                │
└─────────────────────────────────────────┼────────────────────────────────────────────┘
                                          │ → S3 (payload) + Kafka `raw-messages`
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                     STAGE 2 — PROCESSORS                                            │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐               │
│  │  Email        │ │  Teams Chat  │ │  Trade Feed   │ │  Social      │               │
│  │  Processor    │ │  Processor   │ │  Processor    │ │  Processor   │               │
│  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘ └──────┬───────┘               │
│         └────────────────┴────────────────┴────────────────┘                         │
└────────────────────────────────────┼─────────────────────────────────────────────────┘
                                     │ → Kafka `parsed-messages`
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                     STAGE 3 — INGESTION / NORMALIZATION                             │
│  ┌─────────────────────┐    ┌──────────────────────┐                                │
│  │  IngestionService    │───▶│  NormalizerRegistry   │                                │
│  │  (Kafka consumer)    │    │  EmailNormalizer      │                                │
│  │                      │    │  TradeNormalizer      │                                │
│  │                      │    │  SocialNormalizer     │                                │
│  │                      │    │  ...                  │                                │
│  └──────────┬───────────┘    └────────────────────────┘                                │
└─────────────┼────────────────────────────────────────────────────────────────────────┘
              │ → Kafka `normalized-messages` + S3
              ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                     LOGSTASH + ELASTICSEARCH                                        │
│  ┌──────────────────┐        ┌──────────────────────────────────────────────────┐   │
│  │  Logstash         │──────▶│  Elasticsearch Cluster                           │   │
│  │  (Kafka consumer, │       │  indices: messages-*, alerts-*, audit-*          │   │
│  │   transforms,     │       └──────────────────────────────────────────────────┘   │
│  │   index to ES)    │                                                              │
│  └──────────────────┘                                                               │
└──────────────────────────────────┬──────────────────────────────────────────────────┘
                                   │
                   ┌───────────────┼───────────────┐
                   ▼               │               ▼
┌──────────────────────────────┐   │  ┌───────────────────────────────────────────────┐
│         PostgreSQL            │   │  │                 UI LAYER                      │
│  users, policies, alerts,     │   │  │  UI Backend (FastAPI) + Frontend (React)     │
│  entities, review queues,     │   │  │                                               │
│  agent configs, audit log     │   │  │  ┌─────────────────────────────────────────┐ │
└──────────┬───────────────────┘   │  │  │  Agent Builder (no-code config UI)      │ │
           │                       │  │  │  Create, edit, test agents from the UI   │ │
           │                       │  │  └─────────────────┬───────────────────────┘ │
           │                       │  └───────────────────┬┼──────────────────────────┘
           │                       ▼                      ││
           │       ┌──────────────────────────────────────────────────────────────────┐
           │       │         AI ANALYTICS LAYER                            ▲          │
           │       │                                          agent configs│          │
           └──────▶│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
                   │  │ Agent        │  │ Pre-built   │  │ Tool        │             │
                   │  │ Runtime      │  │ Agents      │  │ Catalog     │             │
                   │  │ (LangChain   │  │ (comms,     │  │ (ES search, │             │
                   │  │  execution)  │  │  trade,     │  │  SQL query, │             │
                   │  │              │  │  anomaly)   │  │  entity     │             │
                   │  └──────────────┘  └─────────────┘  │  lookup)    │             │
                   │                                      └─────────────┘             │
                   │  Queries: Elasticsearch ◀──────────────────────────────────────▶ │
                   │  Queries: PostgreSQL    ◀──────────────────────────────────────▶ │
                   └──────────────────────────────────────────────────────────────────┘
```

## Project Structure

- `connectors/`: Data source connectors and the shared framework.
  - `connector-framework/`: Base classes and shared schema (`umbrella-connector-framework`).
  - `email/`: IMAP/SMTP connector implementation.
  - Additional connectors for other data sources (trade feeds, social media, etc.).
- `ingestion-api/`: Centralized service for normalization and dual-writing.
- `processing/`: Services for enrichment (Transcription, Translation, NLP).
- `agents/`: LangChain agent runtime, tool definitions, and pre-built agent configs.
- `ui/`: Analytics dashboard + agent builder UI (Frontend & Backend).
- `infrastructure/`: Deployment configurations for Kafka, Elasticsearch, PostgreSQL, etc.
- `deploy/`: Kubernetes manifests.

## Key Components

### Connector Layer
Standalone microservices responsible for interfacing with data sources. They use a common framework for health checks, retries, and dead-letter routing.

### Ingestion API
A centralized gateway that normalizes incoming parsed data into a unified schema and persists it to both Kafka and S3.

### Processing Layer
- **Transcription Service**: Converts audio to text with speaker diarization.
- **Translation Service**: Detects languages and translates content to English.
- **NLP Service**: Performs lexicon matching, entity recognition, sentiment analysis, and alert generation.

### AI Analytics Layer
- **General Analytics**: Deduplication, email threading, outlier detection, entity resolution, and NLP enrichment pipelines that run automatically on ingested data.
- **Audio Transcription**: Whisper-based speech-to-text with speaker diarization for calls, voicemails, and recordings.
- **Agent Runtime**: LangChain/LangGraph execution engine — loads agent configs from PostgreSQL, runs them with memory, tool calling, and structured output.
- **Tool Catalog**: Pre-built tools for Elasticsearch queries (full-text, aggregations, vector search) and PostgreSQL queries (SQL, entity resolution).
- **Audit Trail**: Every agent query, reasoning step, and output is logged.

### UI Layer
- **Dashboard**: React frontend + FastAPI backend for data exploration, alerts, and review workflows.
- **Agent Builder**: No-code UI for creating, editing, and testing custom AI agents. Configs are stored in PostgreSQL and executed by the AI analytics layer.

### Search & Storage
- **Elasticsearch**: Full-text search and indexing of all ingested data and alerts.
- **PostgreSQL**: Application state — users, policies, agent configurations, entities, audit log.
- **S3**: Long-term retention of raw, normalized, and processed data.

## Development Setup

The project uses `uv` for Python environment management.

```bash
# Install all packages in editable mode
pip install -e connectors/connector-framework/ -e connectors/email/ -e ingestion-api/
```

### Local Infrastructure
Start required services using Docker Compose:

```bash
# Kafka (KRaft single-node)
cd infrastructure/kafka && docker compose up -d

# Elasticsearch + Logstash
cd infrastructure/elasticsearch && docker compose up -d
```

## Running Services

```bash
# Email connector (Stage 1: IMAP → S3 + Kafka)
python -m umbrella_email connector

# Email processor (Stage 2: Kafka → parse → Kafka)
python -m umbrella_email processor

# Ingestion service (Stage 3: normalize parsed → Kafka + S3)
python -m umbrella_ingestion
```

## Testing

```bash
# All tests for a package
pytest connectors/connector-framework/tests/ -v
pytest connectors/email/tests/ -v
pytest ingestion-api/tests/ -v
```

## Technology Stack

| Layer | Technology |
|---|---|
| Languages | Python, TypeScript |
| AI / Agents | LangChain, LangGraph — model-agnostic (OpenAI, Anthropic, self-hosted via vLLM/Ollama, etc.) |
| Frameworks | FastAPI, React, Pydantic |
| Message Bus | Apache Kafka |
| Search | Elasticsearch |
| Database | PostgreSQL |
| Object Storage | S3 (MinIO for local) |
| Containerization | Docker, Kubernetes |
| CI/CD | GitHub Actions |

## Deployment

Kubernetes manifests are organized by namespace in `deploy/k8s/`:
- `umbrella-streaming`: Kafka
- `umbrella-storage`: Elasticsearch, Logstash, MinIO, PostgreSQL
- `umbrella-connectors`: Connector and Processor deployments
- `umbrella-ingestion`: Ingestion Service
- `umbrella-ui`: UI Backend + Frontend

## Screenshots

### Dashboard
![Dashboard](docs/screenshots/ss_dashboard.png)

### Alerts
![Alerts](docs/screenshots/ss_alerts.png)

### Message Search
![Message Search](docs/screenshots/ss_search.png)

### Message Review
![Message Review](docs/screenshots/ss_message_review.png)

### Review Queues
![Review Queues](docs/screenshots/ss_review_queues.png)

### Entities
![Entities](docs/screenshots/ss_entities.png)

### Entity Detail
![Entity Detail](docs/screenshots/ss_single_entity.png)

### Policies
![Policies](docs/screenshots/ss_policies.png)

### RBAC
![RBAC](docs/screenshots/ss_rbac.png)

### Audit Log
![Audit Log](docs/screenshots/ss_audit_log.png)
