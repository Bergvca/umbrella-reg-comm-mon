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

## 1. Overview

Umbrella is a regulatory communications monitoring platform designed to capture, normalize, process, and surface electronic communications (eComm) and audio communications (aComm) for compliance review. The platform ingests data from multiple communication channels, applies NLP and transcription pipelines, and presents flagged alerts to compliance reviewers through a custom UI.

The system follows a **microservices architecture** deployed on **Kubernetes**, ensuring each component can be developed, scaled, and deployed independently.

---

## 2. Architecture & Data Flow

### Three-Stage Pipeline Pattern

All communication channels follow the same **three-stage pipeline**. This pattern has been fully implemented for **Email** and must be replicated for every additional channel.

```
Channel (IMAP, Graph API, SAPI, ...)
    │
    ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  STAGE 1 — CONNECTOR                                                        │
│  Poll/stream the external system. Store large payloads in S3 using the      │
│  claim-check pattern. Publish RawMessage to Kafka `raw-messages`.           │
│                                                                              │
│  Implemented via BaseConnector framework (Kafka producer, S3, health,       │
│  dead-letter handler, retry logic, asyncio.TaskGroup).                      │
│  New connectors: subclass BaseConnector, implement ingest() async generator.│
└──────────┬───────────────────────────────────────────────────────────────────┘
           │  RawMessage → S3 (payload) + Kafka `raw-messages` (pointer)
           ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  STAGE 2 — PROCESSOR                                                        │
│  Consume from `raw-messages`. Download payload from S3. Parse the           │
│  channel-specific format into structured data. Publish to Kafka             │
│  `parsed-messages`.                                                          │
│                                                                              │
│  Each channel has its own processor (e.g. EmailProcessor parses EML →       │
│  headers, body, attachments).                                                │
└──────────┬───────────────────────────────────────────────────────────────────┘
           │  Structured/parsed data → Kafka `parsed-messages`
           ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  STAGE 3 — INGESTION / NORMALIZATION                                        │
│  Consume from `parsed-messages`. Run the appropriate channel normalizer     │
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

### Full Pipeline per Channel

```
Email (IMAP)  ──▶ EmailConnector ──▶ S3 + Kafka(raw-messages)
                  ──▶ EmailProcessor ──▶ Kafka(parsed-messages)
                  ──▶ IngestionService (EmailNormalizer) ──▶ Kafka(normalized-messages) + S3
                  ──▶ Logstash ──▶ Elasticsearch                          ✅ IMPLEMENTED

Teams Chat    ──▶ TeamsChatConnector ──▶ S3 + Kafka(raw-messages)
                  ──▶ TeamsChatProcessor ──▶ Kafka(parsed-messages)
                  ──▶ IngestionService (TeamsNormalizer) ──▶ ...           ⬚ TODO

Teams Calls   ──▶ TeamsCallConnector ──▶ S3 + Kafka(raw-messages)
                  ──▶ TeamsCallProcessor ──▶ Kafka(parsed-messages)
                  ──▶ IngestionService (TeamsCallNormalizer) ──▶ ...       ⬚ TODO

Unigy Turret  ──▶ UnigyConnector ──▶ S3 + Kafka(raw-messages)
                  ──▶ UnigyProcessor ──▶ Kafka(parsed-messages)
                  ──▶ IngestionService (TurretNormalizer) ──▶ ...          ⬚ TODO

Bloomberg Chat──▶ BBChatConnector ──▶ S3 + Kafka(raw-messages)
                  ──▶ BBChatProcessor ──▶ Kafka(parsed-messages)
                  ──▶ IngestionService (BloombergNormalizer) ──▶ ...       ⬚ TODO

Bloomberg Email─▶ BBEmailConnector ──▶ S3 + Kafka(raw-messages)
                  ──▶ BBEmailProcessor ──▶ Kafka(parsed-messages)
                  ──▶ IngestionService (BloombergEmailNormalizer) ──▶ ...  ⬚ TODO
```

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                         STAGE 1 — CONNECTORS                                        │
│                                                                                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐    │
│  │  Teams    │ │  Teams   │ │  Unigy   │ │Bloomberg │ │Bloomberg │ │  Email   │    │
│  │  Chat     │ │  Calls   │ │  Turret  │ │  Chat    │ │  Email   │ │  (IMAP)  │    │
│  │ Connector │ │ Connector│ │ Connector│ │ Connector│ │ Connector│ │ Connector │    │
│  │  ⬚ TODO  │ │  ⬚ TODO │ │  ⬚ TODO │ │  ⬚ TODO │ │  ⬚ TODO │ │  ✅ DONE │    │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘    │
│       └─────────────┴────────────┴──────┬──────┴─────────────┴────────────┘          │
│                                         │                                            │
│                              ┌──────────┴──────────┐                                 │
│                              │   BaseConnector      │   Shared framework:             │
│                              │   Framework          │   Kafka, S3, health,            │
│                              │                      │   DLQ, retry, TaskGroup         │
│                              └──────────┬───────────┘                                │
└─────────────────────────────────────────┼────────────────────────────────────────────┘
                                          │ → S3 (payload) + Kafka `raw-messages`
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                         STAGE 2 — PROCESSORS                                        │
│                                                                                     │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐               │
│  │  Email        │ │  Teams Chat  │ │  Teams Call   │ │  Bloomberg   │               │
│  │  Processor    │ │  Processor   │ │  Processor    │ │  Processor   │               │
│  │  ✅ DONE      │ │  ⬚ TODO     │ │  ⬚ TODO      │ │  ⬚ TODO     │               │
│  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘ └──────┬───────┘               │
│         └────────────────┴────────────────┴────────────────┘                         │
│                                    │                                                 │
└────────────────────────────────────┼─────────────────────────────────────────────────┘
                                     │ → Kafka `parsed-messages`
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                         STAGE 3 — INGESTION / NORMALIZATION                         │
│                                                                                     │
│  ┌─────────────────────┐    ┌──────────────────────┐                                │
│  │  IngestionService    │───▶│  NormalizerRegistry   │                                │
│  │  (Kafka consumer)    │    │                        │                                │
│  │                      │    │  EmailNormalizer  ✅   │                                │
│  │                      │    │  TeamsNormalizer  ⬚   │                                │
│  │                      │    │  BloombergNorm.  ⬚   │                                │
│  │                      │    │  TurretNorm.    ⬚   │                                │
│  └──────────┬───────────┘    └────────────────────────┘                                │
│             │                                                                        │
└─────────────┼────────────────────────────────────────────────────────────────────────┘
              │ → Kafka `normalized-messages` + S3
              ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                         LOGSTASH + ELASTICSEARCH                                    │
│                                                                                     │
│  ┌──────────────────┐        ┌──────────────────────────────────────────────────┐   │
│  │  Logstash         │──────▶│  Elasticsearch Cluster                           │   │
│  │  (Kafka consumer, │       │                                                  │   │
│  │   transforms,     │       │  indices:                                        │   │
│  │   index to ES)    │       │    messages-*   — normalized + enriched messages  │   │
│  └──────────────────┘        │    alerts-*     — generated alerts w/ scores      │   │
│                              │    audit-*      — reviewer actions / audit trail  │   │
│                              └──────────────────────────────────────────────────┘   │
│                                                                                     │
└──────────────────────────────────┬──────────────────────────────────────────────────┘
                                   │
                   ┌───────────────┼───────────────┐
                   ▼               │               ▼
┌──────────────────────────────┐   │  ┌───────────────────────────────────────────────────┐
│         PostgreSQL            │   │  │                    UI LAYER                        │
│                               │   │  │                                                   │
│  tables:                      │   │  │  ┌────────────────────┐  ┌─────────────────────┐  │
│    users / roles              │   │  │  │ UI Backend (API)   │  │ Frontend (SPA)      │  │
│    policies / lexicons        │   │  │  │                    │  │                     │  │
│    review_queues / batches    │   │  │  │ • Query ES         │  │ • Alert dashboard   │  │
│    alerts                     │   │  │  │ • CRUD on PG       │  │ • Message search    │  │
│    entities / entity_links    │   │  │  │ • Auth / RBAC      │  │ • Entity resolution │  │
│    alert_generation_jobs      │   │  │  │ • Export/reporting  │  │ • Policy config     │  │
│    review_decisions           │   │  │  └────────┬───────────┘  │ • Review queues     │  │
│    audit_log                  │   │  │           │              │ • Audit trail       │  │
│                               │   │  │           │              └─────────────────────┘  │
└──────────────────────────────┘   │  │           │                                       │
                                   │  └───────────┼───────────────────────────────────────┘
                                   │              │
                                   ▼              ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                    ANALYTICS & AI LAYER  ⬚ NOT YET IMPLEMENTED                      │
│                                                                                     │
│  ┌──────────────────────────┐  ┌──────────────────────────┐  ┌───────────────────┐  │
│  │  RAG Search Engine        │  │  Agentic Review          │  │  Agent Context    │  │
│  │                           │  │                           │  │  Enrichment       │  │
│  │  • Vector embeddings of   │  │  • AI agent auto-reviews  │  │                   │  │
│  │    all indexed messages   │  │    flagged alerts         │  │  • Agent pulls    │  │
│  │  • Semantic search over   │  │  • Drafts disposition     │  │    related comms, │  │
│  │    comms (beyond keyword) │  │    recommendations with   │  │    entity history,│  │
│  │  • Natural-language       │  │    cited evidence         │  │    prior alerts   │  │
│  │    queries ("show me all  │  │  • Escalates ambiguous    │  │  • Builds rich    │  │
│  │    comms about XYZ deal") │  │    cases to human review  │  │    context window │  │
│  │  • Cross-channel context  │  │  • Learns from reviewer   │  │    for reviewer   │  │
│  │    retrieval              │  │    feedback loop          │  │  • Surfaces prior │  │
│  │                           │  │  • Configurable autonomy  │  │    decisions on   │  │
│  │  Vector DB:               │  │    levels per policy      │  │    similar comms  │  │
│  │  pgvector / Qdrant /      │  │                           │  │                   │  │
│  │  Weaviate                 │  │  LLM: Claude / minimax    │  │  Feeds into RAG   │  │
│  └──────────────────────────┘  └──────────────────────────┘  └───────────────────┘  │
│                                                                                     │
│  ┌──────────────────────────────────────────────────────────────────────────────┐    │
│  │  Agentic Workflow Orchestrator                                               │    │
│  │                                                                              │    │
│  │  • Orchestrates multi-step review workflows using tool-calling LLM agents   │    │
│  │  • Tools: ES search, RAG retrieval, entity lookup, policy check, PG query   │    │
│  │  • Autonomous triage: low-risk auto-close, medium-risk enrich, high-risk    │    │
│  │    escalate with full context package for human reviewer                     │    │
│  │  • Audit trail of all agent reasoning steps and decisions                   │    │
│  └──────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Kafka Topics

| Topic | Producer | Consumer(s) |
|---|---|---|
| `raw-messages` | Connectors (Stage 1) | Processors (Stage 2) |
| `parsed-messages` | Processors (Stage 2) | IngestionService (Stage 3) |
| `normalized-messages` | IngestionService (Stage 3) | Logstash → ES |
| `processing-results` | Processing services (future) | ES indexer |
| `alerts` | NLP / alert generation | ES indexer, UI backend |
| `dead-letter` | Any stage (on failure) | Monitoring / manual review |
| `normalized-messages-dlq` | Logstash (on failure) | Monitoring / manual review |

---

## 4. Component Details

### 4.1 Connector Layer (Stage 1)

Each connector is a standalone microservice responsible for interfacing with a single communication channel. Connectors share a common base class (`BaseConnector`) that provides Kafka producer, S3 client, health server, dead-letter handler, and retry logic via `asyncio.TaskGroup`.

| Connector | Channel Type | Integration Method | Data Type | Status |
|---|---|---|---|---|
| Email (IMAP) | eComm | IMAP polling | Text, attachments (EML) | ✅ Done |
| Teams Chat | eComm | Microsoft Graph API (webhooks + polling) | Text, attachments | ⬚ TODO |
| Teams Calls | aComm | Microsoft Graph Call Records API | Audio (WAV/OGG) | ⬚ TODO |
| Unigy Turret | aComm | Unigy REST/SFTP export | Audio (WAV) | ⬚ TODO |
| Bloomberg Chat | eComm | Bloomberg SAPI / B-Pipe | Text, attachments | ⬚ TODO |
| Bloomberg Email | eComm | Bloomberg MSG export / SFTP | Text, attachments | ⬚ TODO |

**Adding a new connector:** Subclass `BaseConnector`, implement `ingest() -> AsyncIterator[RawMessage]`, and deploy as a new Kubernetes deployment. The framework handles Kafka production, S3 upload, retry logic, and dead-letter routing.

### 4.2 Processor Layer (Stage 2)

Each processor consumes `RawMessage` records from Kafka `raw-messages`, downloads the payload from S3, parses the channel-specific format into structured data, and publishes to Kafka `parsed-messages`.

| Processor | Input Format | Output | Status |
|---|---|---|---|
| EmailProcessor | EML files (RFC 5322) | Headers, body, attachments | ✅ Done |
| TeamsChatProcessor | Graph API JSON | Messages, reactions, threads | ⬚ TODO |
| TeamsCallProcessor | Call recording + metadata | Audio ref + call metadata | ⬚ TODO |
| UnigyProcessor | WAV + call metadata | Audio ref + turret metadata | ⬚ TODO |
| BloombergChatProcessor | SAPI messages | Chat messages, attachments | ⬚ TODO |
| BloombergEmailProcessor | MSG export | Headers, body, attachments | ⬚ TODO |

### 4.3 Ingestion / Normalization (Stage 3)

The `IngestionService` consumes from `parsed-messages`, selects the appropriate normalizer from the `NormalizerRegistry` based on `Channel`, and produces a `NormalizedMessage` in the canonical schema. It dual-writes to Kafka `normalized-messages` and S3.

**Normalized message schema:**
```json
{
  "message_id":    "string",
  "channel":       "enum (email, teams_chat, teams_call, bloomberg, turret, ...)",
  "direction":     "inbound | outbound | internal",
  "timestamp":     "ISO-8601",
  "participants":  [{ "id", "name", "role" }],
  "body_text":     "string | null",
  "audio_ref":     "S3 URI | null",
  "attachments":   [{ "name", "type", "s3_uri" }],
  "metadata":      { "channel-specific fields" }
}
```

**Adding a new normalizer:** Subclass `BaseNormalizer`, implement the normalization logic, and register in the `NormalizerRegistry` mapping `Channel` → normalizer class.

### 4.4 Message Bus (Kafka)

Apache Kafka (KRaft mode, single-node dev / 3-broker prod) acts as the central nervous system. At-least-once delivery ensures no messages are lost. Each stage consumes independently at its own pace.

### 4.5 Raw Storage (S3 / MinIO)

All data is persisted to S3 for long-term retention and regulatory audit requirements:

- `/raw/` — original payloads as received from connectors (claim-check)
- `/normalized/` — normalized JSON records
- `/audio/` — audio files (calls) referenced by `audio_ref`

Lifecycle policies enforce retention periods per regulatory requirements (e.g., 7 years for FINRA/MiFID II).

### 4.6 Processing Layer (Future)

Three independent microservices will consume from Kafka and publish enriched results back:

#### Transcription Service
- Consumes messages with `audio_ref` set
- Downloads audio from S3, runs speech-to-text (e.g., Whisper, Azure Speech)
- Performs speaker diarization to attribute utterances to participants
- Publishes transcript back to `processing-results`

#### Translation Service
- Detects language of `body_text` or transcript
- Translates non-primary-language content to English (configurable)
- Publishes translated text alongside original to `processing-results`

#### NLP Service
- **Lexicon / keyword matching** — configurable watchlists
- **Named entity recognition** — people, organizations, securities, monetary values
- **Sentiment analysis** — flag aggressive or unusual tone
- **Intent classification** — detect potential policy violations
- **Alert generation** — score each message against configured policies, generate alerts above threshold
- Publishes enriched records to `processing-results` and alerts to `alerts`

### 4.7 Search & Storage Layer

#### Elasticsearch Cluster
- Logstash consumes `normalized-messages` from Kafka, transforms, and indexes into ES
- Stores messages for full-text and structured search
- Stores generated alerts with risk scores, matched policies, and highlighted excerpts
- Maintains audit trail of reviewer actions

#### PostgreSQL
- Stores application state: user accounts, RBAC, review decisions
- Manages review queues, batches, and alert generation jobs
- Holds policy/lexicon configuration
- Entity resolution tables (entities, entity_links)
- Audit log

### 4.8 UI Layer

A custom single-page application backed by a FastAPI server.

**UI Backend (API)**
- Queries Elasticsearch for message search and retrieval
- CRUD operations on PostgreSQL for alerts, policies, queues, entities
- Alert generation (ES percolator queries against policies)
- Handles authentication (SSO/OIDC) and role-based access control
- Provides export/reporting endpoints

**Frontend (SPA — React + TypeScript)**
- **Alert Review Dashboard** — queue of alerts sorted by risk score, filterable by channel, date, policy
- **Message Search** — full-text search across all indexed communications
- **Entity Resolution** — view and manage resolved entities across channels
- **Review Queues** — batch-based review workflow
- **Policy Configuration** — manage lexicons, rules, and thresholds
- **Audit Trail** — full log of who reviewed what and when

### 4.9 Analytics & AI Layer (Future)

> **Not yet implemented.** This layer sits on top of ES + PG and powers intelligent search, automated review, and context enrichment.

#### RAG Search Engine
- Generate vector embeddings for all indexed messages (body text, transcripts, attachments)
- Enable **semantic search** beyond keyword matching — natural-language queries like "show me all comms discussing the XYZ acquisition" return relevant results even without exact keyword matches
- **Cross-channel context retrieval** — find related conversations across email, chat, and voice for a given entity, topic, or time window
- Vector store options: pgvector (co-located with PG), Qdrant, or Weaviate
- Embedding models: OpenAI `text-embedding-3-large`, Cohere, or self-hosted (e.g. BGE)

#### Agentic Review
- AI agent **automatically reviews flagged alerts** using tool-calling LLM (Claude / GPT-4)
- Agent has access to tools: ES search, RAG retrieval, entity lookup, policy definitions, PG queries, prior review decisions
- For each alert, the agent:
  1. Retrieves the flagged message + surrounding conversation context
  2. Pulls entity history, prior alerts, and related comms via RAG
  3. Evaluates against applicable policies
  4. Drafts a **disposition recommendation** with cited evidence
- **Configurable autonomy levels** per policy type:
  - *Auto-close*: low-risk alerts (e.g. false-positive keyword hits) closed automatically with audit trail
  - *Enrich & recommend*: medium-risk alerts enriched with context, recommendation drafted for human reviewer
  - *Escalate*: high-risk alerts packaged with full context and escalated immediately
- Learns from reviewer feedback — accepted/overturned recommendations feed back into prompt tuning and threshold calibration

#### Agent Context Enrichment
- When a human reviewer opens an alert, an agent **pre-builds a rich context package**:
  - Related communications from the same participants (across all channels)
  - Entity profile: role, department, communication patterns, prior alert history
  - Prior review decisions on similar messages or involving the same entities
  - Policy explanation and relevant regulatory guidance
- Surfaces **"reviewers who saw similar alerts decided..."** patterns to reduce review time
- Context is assembled on-demand via RAG retrieval + structured PG queries

#### Agentic Workflow Orchestrator
- Orchestrates multi-step review workflows using tool-calling LLM agents
- Available tools: ES search, RAG retrieval, entity lookup, policy check, PG query, case creation
- Full audit trail of all agent reasoning steps, tool calls, and decisions for regulatory defensibility
- Human-in-the-loop: agents never take final action on high-risk items without human approval

---

## 5. Kubernetes Deployment Model

```
┌─────────────────────────────────────────────────────────┐
│                   Kubernetes Cluster                     │
│                                                         │
│  namespace: umbrella-connectors                        │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │teams-chat│ │teams-call│ │  unigy   │ │bloomberg │  │
│  │ deploy   │ │ deploy   │ │  deploy  │ │  deploy  │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘  │
│  ┌──────────┐ ┌──────────┐                              │
│  │bb-email  │ │  email   │  (connector + processor)     │
│  │ deploy   │ │  deploy  │                              │
│  └──────────┘ └──────────┘                              │
│                                                         │
│  namespace: umbrella-ingestion                         │
│  ┌──────────────────────┐                               │
│  │  ingestion-service   │  (HPA: 2–10 replicas)        │
│  └──────────────────────┘                               │
│                                                         │
│  namespace: umbrella-streaming                         │
│  ┌──────────────────────┐                               │
│  │  kafka (StatefulSet) │  (KRaft, 3 brokers prod)     │
│  └──────────────────────┘                               │
│                                                         │
│  namespace: umbrella-processing                        │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐    │
│  │ transcription│ │ translation  │ │     nlp      │    │
│  │  deploy (GPU)│ │   deploy     │ │   deploy     │    │
│  └──────────────┘ └──────────────┘ └──────────────┘    │
│                                                         │
│  namespace: umbrella-storage                           │
│  ┌──────────────────────┐ ┌──────────────────────┐     │
│  │  elasticsearch       │ │  postgresql          │     │
│  │  (StatefulSet)       │ │  (StatefulSet, HA)   │     │
│  └──────────────────────┘ └──────────────────────┘     │
│  ┌──────────────────────┐ ┌──────────────────────┐     │
│  │  logstash            │ │  minio (S3)          │     │
│  │  (Deployment)        │ │  (StatefulSet)       │     │
│  └──────────────────────┘ └──────────────────────┘     │
│                                                         │
│  namespace: umbrella-ui                                │
│  ┌──────────────────────┐ ┌──────────────────────┐     │
│  │  ui-backend          │ │  ui-frontend (nginx) │     │
│  │  deploy (HPA)        │ │  deploy              │     │
│  └──────────────────────┘ └──────────────────────┘     │
│                                                         │
│  namespace: umbrella-analytics  ⬚ FUTURE              │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐    │
│  │ rag-search   │ │ agent-review │ │ vector-db    │    │
│  │  deploy      │ │   deploy     │ │ (pgvector /  │    │
│  │              │ │              │ │  qdrant)     │    │
│  └──────────────┘ └──────────────┘ └──────────────┘    │
│                                                         │
│  namespace: umbrella-infra                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐               │
│  │ ingress  │ │ cert-mgr │ │monitoring│               │
│  │controller│ │          │ │(prom/graf)│              │
│  └──────────┘ └──────────┘ └──────────┘               │
│                                                         │
└─────────────────────────────────────────────────────────┘

         External:  S3 (object storage) / MinIO (on-prem)
```

---

## 6. Technology Summary

| Layer | Technology |
|---|---|
| Connectors | Python async microservices, channel-specific SDKs |
| Connector Framework | `umbrella-connector-framework` (BaseConnector, RawMessage, NormalizedMessage) |
| Ingestion Service | Python (async Kafka consumer), NormalizerRegistry |
| Message Bus | Apache Kafka (KRaft mode) |
| Object Storage | S3 / MinIO (on-prem) |
| Transcription | OpenAI Whisper / Azure Speech Services |
| Translation | Azure Translator / Cloud Translate |
| NLP | spaCy, custom models, lexicon engine |
| Search | Elasticsearch 9.x via Logstash |
| Application DB | PostgreSQL 16 |
| Frontend | React + TypeScript (Vite) |
| UI Backend | Python (FastAPI) |
| Orchestration | Kubernetes (Minikube dev / EKS prod) |
| CI/CD | GitHub Actions, Helm, ArgoCD |
| Observability | Prometheus, Grafana, OpenTelemetry |
| RAG / Vector Search | pgvector or Qdrant + embedding models (future) |
| Agentic AI | Claude / GPT-4 tool-calling agents (future) |

---

## 7. Implementation Status & Next Steps

### Completed
- [x] Normalized message schema (`NormalizedMessage` in connector-framework)
- [x] Connector plugin framework (`BaseConnector`, Kafka, S3, DLQ, retry)
- [x] Email connector (IMAP → S3 + Kafka `raw-messages`)
- [x] Email processor (Kafka `raw-messages` → parse EML → Kafka `parsed-messages`)
- [x] Ingestion service with `EmailNormalizer` (Kafka `parsed-messages` → normalize → Kafka `normalized-messages` + S3)
- [x] Kafka (KRaft single-node) + S3 (MinIO) infrastructure
- [x] Elasticsearch + Logstash (Kafka `normalized-messages` → ES index)
- [x] PostgreSQL schema (users, roles, policies, alerts, entities, review queues, audit)
- [x] UI Backend (FastAPI — ES queries, PG CRUD, alert generation, policies, queues, entities)
- [x] UI Frontend (React — alerts dashboard, message search, entities, policies, review queues)

### Next — Replicate Pipeline for All Channels
1. **Teams Chat** — connector (Graph API polling/webhooks), processor (JSON → structured), normalizer
2. **Teams Calls** — connector (Call Records API), processor (recording + metadata), normalizer
3. **Bloomberg Chat** — connector (SAPI/B-Pipe), processor (SAPI messages → structured), normalizer
4. **Bloomberg Email** — connector (MSG export/SFTP), processor (MSG → structured), normalizer
5. **Unigy Turret** — connector (REST/SFTP), processor (WAV + metadata), normalizer

### Future Processing Services
6. **Transcription service** — speech-to-text + diarization for audio channels
7. **Translation service** — language detection + translation for multilingual content
8. **NLP service** — lexicon matching, NER, sentiment, intent classification, alert generation

### Analytics & AI Layer
9. **RAG search engine** — vector embeddings of all messages, semantic search, cross-channel context retrieval
10. **Agentic review** — AI agents auto-review alerts, draft dispositions with cited evidence, configurable autonomy levels
11. **Agent context enrichment** — pre-build rich context packages for human reviewers (related comms, entity history, prior decisions)
12. **Agentic workflow orchestrator** — multi-step review workflows with tool-calling LLM agents, full audit trail

### Platform Maturity
13. **Auth / SSO** — OIDC integration for UI
14. **Case management** — case escalation workflow + external CM integration
15. **Observability** — Prometheus + Grafana dashboards, OpenTelemetry tracing
16. **Production hardening** — HA Kafka (3-broker), ES cluster sizing, HPA tuning
