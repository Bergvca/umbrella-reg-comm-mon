# Umbrella — Regulatory Communications Monitoring Platform

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
       ╱  ╱  ╱  ╱        │  comms    │         ╲  ╲  ╲  ╲
     ╱  ╱  ╱  ╱          └───────────┘           ╲  ╲  ╲  ╲
```

## Overview

Umbrella is a regulatory communications monitoring platform designed to capture, normalize, process, and surface electronic communications (eComm) and audio communications (aComm) for compliance review. The platform ingests data from multiple communication channels, applies NLP and transcription pipelines, and presents flagged alerts to compliance reviewers through a custom UI.

The system follows a **microservices architecture** deployed on **Kubernetes**, ensuring each component can be developed, scaled, and deployed independently.

## Pipeline Architecture

The system uses a multi-stage message flow to handle data from various sources:

```
Connectors → Kafka(raw-messages) → Processors → Kafka(parsed-messages)
    → IngestionService → Kafka(normalized-messages) → Logstash → Elasticsearch
```

1.  **Connectors** (e.g. `EmailConnector`) poll external systems, store large payloads in S3 (claim-check pattern), and publish `RawMessage` to Kafka `raw-messages`.
2.  **Processors** (e.g. `EmailProcessor`) consume `raw-messages`, download from S3, parse them, and publish structured data to `parsed-messages`.
3.  **Ingestion Service** consumes `parsed-messages`, runs channel-specific normalizers to produce `NormalizedMessage`, and dual-writes to Kafka `normalized-messages` + S3.

## Project Structure

- `connectors/`: Channel-specific connectors and the shared framework.
  - `connector-framework/`: Base classes and shared schema (`umbrella-connector-framework`).
  - `email/`: IMAP/SMTP connector implementation.
  - `teams-chat/`, `teams-calls/`, `bloomberg-chat/`, etc.: Future connector implementations.
- `ingestion-api/`: Centralized service for normalization and dual-writing.
- `processing/`: Services for enrichment (Transcription, Translation, NLP).
- `ui/`: Compliance review dashboard (Frontend & Backend).
- `infrastructure/`: Deployment configurations for Kafka, Elasticsearch, PostgreSQL, etc.
- `deploy/`: Kubernetes manifests and Helm charts.
- `scripts/`: Utility scripts for development and testing.

## Key Components

### Connector Layer
Standalone microservices responsible for interfacing with communication channels. They use a common framework for health checks, retries, and dead-letter routing.

### Ingestion API
A centralized gateway that normalizes incoming parsed messages into a unified schema and persists them to both Kafka and S3.

### Processing Layer
- **Transcription Service**: Converts audio (calls) to text with speaker diarization.
- **Translation Service**: Detects languages and translates content to English.
- **NLP Service**: Performs lexicon matching, entity recognition, sentiment analysis, and alert generation.

### Search & Storage
- **Elasticsearch**: Full-text search and indexing of enriched messages and alerts.
- **PostgreSQL**: Stores application state, users, cases, and policy configurations.
- **S3**: Long-term retention of raw, normalized, and processed data.

## Development Setup

The project uses `uv` for python environment management.

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
| Languages | Python, Go, TypeScript |
| Frameworks | FastAPI, React, Pydantic |
| Message Bus | Apache Kafka |
| Search | Elasticsearch |
| Database | PostgreSQL |
| Object Storage | S3 (MinIO for local) |
| Containerization | Docker, Kubernetes |
| CI/CD | GitHub Actions, Helm |

## Deployment

Kubernetes manifests are organized by namespace in `deploy/k8s/`:
- `umbrella-streaming`: Kafka
- `umbrella-storage`: Elasticsearch, Logstash, MinIO
- `umbrella-connectors`: Connector and Processor deployments
- `umbrella-ingestion`: Ingestion Service
