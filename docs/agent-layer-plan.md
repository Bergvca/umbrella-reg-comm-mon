# Agent Layer — Implementation Plan

This document describes the design and implementation plan for Umbrella's AI agent layer: the **Agent Builder UI** (in the UI layer) and the **Agent Runtime** (in the AI analytics layer). Together they let users create, configure, test, and run custom LangChain agents that query Elasticsearch and PostgreSQL — without writing code.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Data Model (PostgreSQL)](#2-data-model-postgresql)
3. [Agent Runtime Service](#3-agent-runtime-service)
4. [Tool Catalog](#4-tool-catalog)
5. [Backend API (UI Backend)](#5-backend-api-ui-backend)
6. [Frontend — Agent Builder UI](#6-frontend--agent-builder-ui)
7. [Natural Language Search](#7-natural-language-search)
8. [Pre-built Agents](#8-pre-built-agents)
9. [Observability & Audit](#9-observability--audit)
10. [Security](#10-security)
11. [Deployment](#11-deployment)
12. [Implementation Phases](#12-implementation-phases)

---

## 1. Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│  UI LAYER                                                            │
│                                                                      │
│  Frontend (React)              Backend (FastAPI)                     │
│  ┌────────────────────┐        ┌──────────────────────────────┐     │
│  │  Agent Builder UI   │──API──▶│  /api/v1/agents/*             │     │
│  │  - List / CRUD      │        │  /api/v1/agent-tools/*        │     │
│  │  - Config editor    │        │  /api/v1/agent-runs/*         │     │
│  │  - Test playground  │        │                                │     │
│  │  - Run history      │        │  Validates configs, proxies    │     │
│  └────────────────────┘        │  execution to Agent Runtime    │     │
│                                 └──────────────┬─────────────────┘     │
└────────────────────────────────────────────────┼──────────────────────┘
                                                 │  gRPC / HTTP
                                                 ▼
┌──────────────────────────────────────────────────────────────────────┐
│  AI ANALYTICS LAYER — Agent Runtime Service                          │
│                                                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌───────────────┐               │
│  │ LangChain /  │  │ Tool        │  │ Model Router  │               │
│  │ LangGraph    │  │ Registry    │  │ (LiteLLM)     │               │
│  │ Executor     │  │             │  │               │               │
│  └──────┬───────┘  └──────┬──────┘  └──────┬────────┘               │
│         │                 │                │                         │
│         ▼                 ▼                ▼                         │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Elasticsearch    │    PostgreSQL    │    S3 / Object Store  │    │
│  └───────────────────┴─────────────────┴───────────────────────┘    │
└──────────────────────────────────────────────────────────────────────┘
```

**Key design decisions:**

- The **Agent Runtime** is a standalone service (`agents/`) separate from the UI backend. It owns all LLM interaction, tool execution, and agent orchestration.
- The **UI Backend** (`ui/backend/`) provides CRUD APIs for agent configs and proxies execution requests to the runtime. It never calls LLMs directly.
- **LiteLLM** is used as a model router so agent configs can reference any model provider (OpenAI, Anthropic, self-hosted vLLM/Ollama, etc.) via a uniform interface.
- Agent configs live in **PostgreSQL** (`agent` schema). The runtime loads them on demand.

---

## 2. Data Model (PostgreSQL)

New schema: `agent`. New DB role: `agent_rw` (read/write `agent`; read `iam`, `entity`).

Migration: `V10__agent.sql`

### `agent.models`

Registered LLM endpoints. Admins configure these; agent builders select from them.

| Column | Type | Constraints |
|---|---|---|
| `id` | uuid | PK, default `gen_random_uuid()` |
| `name` | text | UNIQUE NOT NULL — display name, e.g. "GPT-4o", "Claude Sonnet", "Local Llama 3" |
| `provider` | text | NOT NULL — LiteLLM provider key, e.g. `openai`, `anthropic`, `ollama`, `vllm` |
| `model_id` | text | NOT NULL — provider-specific model ID, e.g. `gpt-4o`, `claude-sonnet-4-20250514` |
| `base_url` | text | NULL for cloud providers; endpoint URL for self-hosted |
| `api_key_secret` | text | NULL — reference to K8s secret key (never stored in plaintext) |
| `max_tokens` | int | DEFAULT 4096 |
| `is_active` | boolean | NOT NULL DEFAULT true |
| `created_by` | uuid | FK → `iam.users.id` |
| `created_at` | timestamptz | NOT NULL DEFAULT now() |
| `updated_at` | timestamptz | NOT NULL DEFAULT now() |

### `agent.tools`

Registry of available tools. Seeded with built-in tools; users can add custom tools.

| Column | Type | Constraints |
|---|---|---|
| `id` | uuid | PK, default `gen_random_uuid()` |
| `name` | text | UNIQUE NOT NULL — machine name, e.g. `es_search`, `sql_query` |
| `display_name` | text | NOT NULL |
| `description` | text | NOT NULL — shown to the LLM as the tool description |
| `category` | text | NOT NULL — `builtin` or `custom` |
| `parameters_schema` | jsonb | NOT NULL — JSON Schema defining tool input parameters |
| `is_active` | boolean | NOT NULL DEFAULT true |
| `created_at` | timestamptz | NOT NULL DEFAULT now() |

### `agent.agents`

Core agent definitions.

| Column | Type | Constraints |
|---|---|---|
| `id` | uuid | PK, default `gen_random_uuid()` |
| `name` | text | NOT NULL |
| `description` | text | |
| `model_id` | uuid | NOT NULL, FK → `agent.models.id` |
| `system_prompt` | text | NOT NULL — natural language instructions |
| `temperature` | numeric(3,2) | NOT NULL DEFAULT 0.0 |
| `max_iterations` | int | NOT NULL DEFAULT 10 — LangChain agent max iterations |
| `output_schema` | jsonb | NULL — if set, enforces structured output |
| `is_builtin` | boolean | NOT NULL DEFAULT false — pre-built agents shipped with Umbrella |
| `is_active` | boolean | NOT NULL DEFAULT true |
| `created_by` | uuid | FK → `iam.users.id` |
| `created_at` | timestamptz | NOT NULL DEFAULT now() |
| `updated_at` | timestamptz | NOT NULL DEFAULT now() |

Unique: `(name, created_by)` — users can have agents with the same name as built-in agents.

### `agent.agent_tools`

Many-to-many: which tools an agent can use.

| Column | Type | Constraints |
|---|---|---|
| `agent_id` | uuid | PK, FK → `agent.agents.id` ON DELETE CASCADE |
| `tool_id` | uuid | PK, FK → `agent.tools.id` ON DELETE CASCADE |
| `tool_config` | jsonb | NULL — per-agent tool overrides (e.g. restrict ES indices, SQL schemas) |

### `agent.agent_data_sources`

Defines which Elasticsearch indices and/or PostgreSQL schemas an agent is allowed to access. This is the security boundary.

| Column | Type | Constraints |
|---|---|---|
| `id` | uuid | PK, default `gen_random_uuid()` |
| `agent_id` | uuid | NOT NULL, FK → `agent.agents.id` ON DELETE CASCADE |
| `source_type` | text | NOT NULL, CHECK IN (`elasticsearch`, `postgresql`) |
| `source_identifier` | text | NOT NULL — ES index pattern (e.g. `messages-*`) or PG schema (e.g. `entity`) |
| `access_mode` | text | NOT NULL DEFAULT `read`, CHECK IN (`read`) |

Unique: `(agent_id, source_type, source_identifier)`

### `agent.runs`

Execution log for every agent invocation.

| Column | Type | Constraints |
|---|---|---|
| `id` | uuid | PK, default `gen_random_uuid()` |
| `agent_id` | uuid | NOT NULL, FK → `agent.agents.id` ON DELETE RESTRICT |
| `status` | text | NOT NULL DEFAULT `pending`, CHECK IN (`pending`, `running`, `completed`, `failed`, `cancelled`) |
| `input` | jsonb | NOT NULL — the user's prompt / input payload |
| `output` | jsonb | NULL — the agent's final response |
| `error_message` | text | NULL |
| `token_usage` | jsonb | NULL — `{ prompt_tokens, completion_tokens, total_tokens }` |
| `iterations` | int | NULL — number of LangChain agent iterations used |
| `duration_ms` | int | NULL |
| `triggered_by` | uuid | NOT NULL, FK → `iam.users.id` |
| `created_at` | timestamptz | NOT NULL DEFAULT now() |
| `completed_at` | timestamptz | NULL |

Indexes: `(agent_id)`, `(triggered_by)`, `(created_at DESC)`, `(status)`

### `agent.run_steps`

Detailed trace of each step within a run (tool calls, LLM reasoning).

| Column | Type | Constraints |
|---|---|---|
| `id` | uuid | PK, default `gen_random_uuid()` |
| `run_id` | uuid | NOT NULL, FK → `agent.runs.id` ON DELETE CASCADE |
| `step_order` | int | NOT NULL |
| `step_type` | text | NOT NULL, CHECK IN (`llm_call`, `tool_call`, `tool_result`) |
| `tool_name` | text | NULL — populated for tool_call / tool_result |
| `input` | jsonb | NOT NULL |
| `output` | jsonb | NULL |
| `token_usage` | jsonb | NULL |
| `duration_ms` | int | NULL |
| `created_at` | timestamptz | NOT NULL DEFAULT now() |

Indexes: `(run_id, step_order)`

---

## 3. Agent Runtime Service

**Package:** `agents/` → installs as `umbrella-agents` (provides `umbrella_agents`)
**Entry point:** `python -m umbrella_agents`
**Framework:** FastAPI (internal service, not exposed publicly)

### Core Components

```
agents/
├── umbrella_agents/
│   ├── __init__.py
│   ├── __main__.py              # uvicorn entrypoint
│   ├── app.py                   # FastAPI app factory
│   ├── config.py                # pydantic-settings (AGENTS_ prefix)
│   ├── executor.py              # Agent execution engine
│   ├── model_router.py          # LiteLLM integration
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── registry.py          # ToolRegistry — maps tool names to implementations
│   │   ├── es_search.py         # Full-text search tool
│   │   ├── es_aggregation.py    # Aggregation/analytics tool
│   │   ├── es_vector_search.py  # Vector similarity search
│   │   ├── sql_query.py         # Read-only SQL query tool
│   │   ├── entity_lookup.py     # Entity resolution lookups
│   │   └── time_series.py       # Time-series analysis tool
│   ├── callbacks/
│   │   ├── __init__.py
│   │   ├── audit.py             # Writes run_steps to DB
│   │   └── streaming.py         # SSE streaming callback
│   ├── db/
│   │   ├── __init__.py
│   │   └── models.py            # SQLAlchemy models for agent schema
│   └── routers/
│       ├── __init__.py
│       ├── execute.py           # POST /execute — run an agent
│       └── health.py            # Health/readiness probes
├── tests/
├── pyproject.toml
└── README.md
```

### Execution Flow

```
1. UI Backend sends POST /execute to Agent Runtime:
   { agent_id, input, triggered_by, stream: bool }

2. Runtime loads agent config from PostgreSQL:
   - agent definition (system_prompt, model, temperature, max_iterations)
   - assigned tools + tool configs
   - allowed data sources

3. Runtime builds a LangChain agent:
   a. Instantiate LLM via LiteLLM (model_router.py)
   b. Build tool list from ToolRegistry, scoped to allowed data sources
   c. Create LangGraph ReAct agent with system prompt and tools

4. Execute agent:
   a. Create agent.runs row (status=running)
   b. Run agent with LangChain callbacks that log each step to agent.run_steps
   c. If streaming, emit SSE events for each intermediate step
   d. On completion, update agent.runs (status, output, token_usage, duration_ms)

5. Return final result to UI Backend
```

### Configuration (`AGENTS_` prefix)

| Env Var | Purpose |
|---|---|
| `AGENTS_PORT` | Service port (default 8001) |
| `AGENTS_DATABASE_URL` | PostgreSQL connection (agent schema) |
| `AGENTS_ES_URL` | Elasticsearch cluster URL |
| `AGENTS_DEFAULT_TIMEOUT` | Max execution time per run (default 120s) |
| `AGENTS_MAX_CONCURRENT_RUNS` | Concurrency limit (default 10) |

---

## 4. Tool Catalog

Each tool is a LangChain `BaseTool` subclass with data-source scoping.

### Built-in Tools

| Tool Name | Description | Data Source |
|---|---|---|
| `es_search` | Full-text search across ES indices using KQL or query DSL. Returns matching documents with highlights. | Elasticsearch |
| `es_aggregation` | Run aggregation queries (terms, date_histogram, stats, etc.) on ES indices. Returns structured aggregation results. | Elasticsearch |
| `es_vector_search` | Semantic similarity search using kNN on vector fields. | Elasticsearch |
| `sql_query` | Execute read-only SQL queries against PostgreSQL. Scoped to allowed schemas. | PostgreSQL |
| `entity_lookup` | Look up entity profiles, handles, and attributes from the entity schema. | PostgreSQL |
| `time_series` | Analyze temporal patterns — volume over time, trend detection, peak identification. Built on ES date_histogram. | Elasticsearch |

### Tool Scoping

Every tool receives a `DataSourceScope` at construction time:

```python
@dataclass
class DataSourceScope:
    allowed_es_indices: list[str]      # e.g. ["messages-*", "alerts-*"]
    allowed_pg_schemas: list[str]      # e.g. ["entity", "alert"]
```

- **ES tools** prepend an index filter to every query, rejecting requests to unauthorized indices.
- **SQL tool** wraps queries in a read-only transaction with `SET search_path` restricted to allowed schemas. Uses a limited-privilege DB role (`agent_readonly`) that only has SELECT grants.

### Custom Tools (Future)

Users will be able to define custom tools via the Agent Builder UI:

- **API Call tool** — HTTP request to an external API with configurable URL template, headers, and response extraction
- **Python Expression tool** — sandboxed Python evaluation for data transformation (using RestrictedPython)

These are stored in `agent.tools` with `category = 'custom'` and executed by the runtime via a generic adapter.

---

## 5. Backend API (UI Backend)

New routers in `ui/backend/umbrella_ui/routers/`. All endpoints require authentication and role-based access.

### Agent CRUD — `/api/v1/agents`

| Method | Path | Role | Description |
|---|---|---|---|
| `GET` | `/api/v1/agents` | reviewer | List agents (with pagination, filters for builtin/custom/active) |
| `GET` | `/api/v1/agents/{id}` | reviewer | Get agent detail (includes tools, data sources) |
| `POST` | `/api/v1/agents` | supervisor | Create agent |
| `PUT` | `/api/v1/agents/{id}` | supervisor | Update agent config |
| `DELETE` | `/api/v1/agents/{id}` | admin | Soft-delete agent (set is_active=false) |
| `POST` | `/api/v1/agents/{id}/clone` | supervisor | Clone an agent (including tools and data sources) |

### Agent Execution — `/api/v1/agent-runs`

| Method | Path | Role | Description |
|---|---|---|---|
| `POST` | `/api/v1/agent-runs` | reviewer | Execute an agent (proxied to runtime). Body: `{ agent_id, input }` |
| `GET` | `/api/v1/agent-runs` | reviewer | List runs (filterable by agent_id, status, triggered_by, date range) |
| `GET` | `/api/v1/agent-runs/{id}` | reviewer | Get run detail including steps |
| `GET` | `/api/v1/agent-runs/{id}/stream` | reviewer | SSE stream for a running agent |
| `POST` | `/api/v1/agent-runs/{id}/cancel` | supervisor | Cancel a running agent |

### Model Management — `/api/v1/agent-models`

| Method | Path | Role | Description |
|---|---|---|---|
| `GET` | `/api/v1/agent-models` | supervisor | List registered models |
| `POST` | `/api/v1/agent-models` | admin | Register a new model endpoint |
| `PUT` | `/api/v1/agent-models/{id}` | admin | Update model config |
| `DELETE` | `/api/v1/agent-models/{id}` | admin | Deactivate model |

### Tool Registry — `/api/v1/agent-tools`

| Method | Path | Role | Description |
|---|---|---|---|
| `GET` | `/api/v1/agent-tools` | supervisor | List available tools (built-in + custom) |

### Request/Response Schemas (Pydantic v2)

```python
# --- Agent Config ---

class AgentCreate(BaseModel):
    name: str
    description: str | None = None
    model_id: uuid.UUID
    system_prompt: str
    temperature: float = 0.0
    max_iterations: int = 10
    output_schema: dict | None = None
    tool_ids: list[uuid.UUID]
    tool_configs: dict[uuid.UUID, dict] | None = None  # tool_id → config overrides
    data_sources: list[DataSourceConfig]

class DataSourceConfig(BaseModel):
    source_type: Literal["elasticsearch", "postgresql"]
    source_identifier: str  # e.g. "messages-*" or "entity"

class AgentResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    model: ModelSummary
    system_prompt: str
    temperature: float
    max_iterations: int
    output_schema: dict | None
    tools: list[ToolSummary]
    data_sources: list[DataSourceConfig]
    is_builtin: bool
    is_active: bool
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

# --- Agent Execution ---

class RunCreate(BaseModel):
    agent_id: uuid.UUID
    input: str  # user prompt

class RunResponse(BaseModel):
    id: uuid.UUID
    agent_id: uuid.UUID
    status: str
    input: dict
    output: dict | None
    error_message: str | None
    token_usage: dict | None
    iterations: int | None
    duration_ms: int | None
    steps: list[RunStepResponse] | None  # included on detail endpoint
    triggered_by: uuid.UUID
    created_at: datetime
    completed_at: datetime | None

class RunStepResponse(BaseModel):
    id: uuid.UUID
    step_order: int
    step_type: str
    tool_name: str | None
    input: dict
    output: dict | None
    token_usage: dict | None
    duration_ms: int | None
    created_at: datetime
```

---

## 6. Frontend — Agent Builder UI

### New Pages

| Route | Component | Description |
|---|---|---|
| `/agents` | `AgentsPage` | List all agents (tabs: My Agents / Built-in / All). Create button. |
| `/agents/new` | `AgentEditorPage` | Multi-step agent creation wizard. |
| `/agents/:id` | `AgentDetailPage` | View agent config, run history, "Run" button. |
| `/agents/:id/edit` | `AgentEditorPage` | Edit existing agent config. |
| `/agents/:id/playground` | `AgentPlaygroundPage` | Interactive test environment. |

### Agent Editor (Create / Edit)

A multi-step form (similar to the existing `GenerateAlertsDialog` wizard pattern):

**Step 1 — Identity**
- Name (text input)
- Description (textarea)

**Step 2 — Model & Behavior**
- Model (dropdown, populated from `/api/v1/agent-models`)
- Temperature (slider, 0.0–1.0)
- Max iterations (number input, 1–50)

**Step 3 — Instructions**
- System prompt (large textarea with markdown preview)
- Template variable insertion (optional, future)

**Step 4 — Tools & Data Sources**
- Available tools displayed as checkboxes with descriptions
- For each selected tool, optional config overrides (collapsible panel)
- Data sources: add Elasticsearch index patterns and/or PostgreSQL schemas

**Step 5 — Output Schema (Optional)**
- Toggle: free-form text output vs. structured JSON
- If structured: JSON Schema editor (code editor with validation)

**Step 6 — Review & Save**
- Summary of all configured fields
- "Save" and "Save & Test" buttons

### Agent Playground

An interactive chat-like interface for testing agents:

```
┌──────────────────────────────────────────────────────────────────┐
│  Agent: Comms Reviewer                        [Config] [History] │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Agent Response                                          │   │
│  │                                                          │   │
│  │  Based on my analysis of the flagged messages, I found   │   │
│  │  3 potential policy violations...                        │   │
│  │                                                          │   │
│  │  ▸ Step 1: es_search("insider trading" index:messages-*) │   │
│  │  ▸ Step 2: entity_lookup(entity_id=...)                  │   │
│  │  ▸ Step 3: sql_query(SELECT ... FROM alert.alerts ...)   │   │
│  │                                                          │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Type your prompt...                              [Send] │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  Tokens: 2,341 prompt / 512 completion  │  Duration: 4.2s       │
└──────────────────────────────────────────────────────────────────┘
```

Features:
- **Streaming** — SSE-based real-time output as the agent thinks and acts
- **Step inspector** — expandable panels showing each tool call's input/output
- **Token counter** — running cost awareness
- **Run history** — sidebar showing previous runs for this agent, click to view

### Agent List Page

- Table with columns: Name, Model, Tools (count), Status (active/inactive), Last Run, Created By
- Filter tabs: My Agents / Built-in / All
- Actions: Edit, Clone, Deactivate, Delete
- "New Agent" button (opens editor)

### Navigation

Add "Agents" to the AppShell sidebar navigation, between "Entities" and "Policies":

```
Dashboard
Alerts
Queues
Messages
Entities
Agents        ← new
Policies
Admin
Audit Log
```

### Frontend File Structure

```
ui/frontend/src/
├── api/
│   └── agents.ts                # API client functions
├── hooks/
│   └── useAgents.ts             # React Query hooks
├── pages/
│   ├── AgentsPage.tsx           # List page
│   ├── AgentDetailPage.tsx      # Detail + run history
│   ├── AgentEditorPage.tsx      # Create / edit wizard
│   └── AgentPlaygroundPage.tsx  # Interactive test UI
└── components/
    └── agents/
        ├── AgentTable.tsx        # Agent list table
        ├── AgentEditorSteps.tsx  # Multi-step form components
        ├── AgentPlayground.tsx   # Chat-like test interface
        ├── RunHistory.tsx        # Run list with status badges
        ├── RunStepInspector.tsx  # Expandable step trace
        ├── ToolSelector.tsx      # Tool picker with config panels
        ├── DataSourcePicker.tsx  # ES index / PG schema selector
        └── SystemPromptEditor.tsx # Textarea with template helpers
```

---

## 7. Natural Language Search

The existing Message Search page (`/messages`) uses keyword/KQL queries against Elasticsearch. Natural language search adds an **AI-powered search mode** where users type a plain-English question, the AI layer translates it into an Elasticsearch query, executes it, and returns results in the same format. This is the first integration point between the existing UI and the agent runtime.

### How It Works

```
User types: "Show me emails from last week where someone discusses quarterly earnings"
                                          │
                                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│  UI Backend — POST /api/v1/messages/nl-search                       │
│                                                                     │
│  1. Send the natural language query + ES index mapping schema       │
│     to the Agent Runtime's query translation endpoint               │
│  2. Agent Runtime calls the LLM with a system prompt that           │
│     instructs it to produce a valid ES query DSL body               │
│  3. LLM returns structured JSON: the ES query + extracted filters   │
│  4. UI Backend validates the returned query (safety check)          │
│  5. UI Backend executes the query against messages-*                │
│  6. Returns standard MessageSearchResponse + the generated query    │
└─────────────────────────────────────────────────────────────────────┘
```

### Agent Runtime — Query Translation Endpoint

New endpoint on the Agent Runtime service:

| Method | Path | Description |
|---|---|---|
| `POST` | `/translate-query` | Translate natural language → ES query DSL |

**Request:**

```json
{
  "natural_language_query": "emails from last week discussing quarterly earnings",
  "index_pattern": "messages-*",
  "field_schema": {
    "body_text": "text",
    "transcript": "text",
    "translated_text": "text",
    "channel": "keyword",
    "direction": "keyword",
    "timestamp": "date",
    "participants.name": "text",
    "participants.id": "keyword",
    "sentiment": "keyword",
    "risk_score": "float"
  }
}
```

**Response:**

```json
{
  "es_query": {
    "query": {
      "bool": {
        "must": [
          {
            "multi_match": {
              "query": "quarterly earnings",
              "fields": ["body_text", "transcript", "translated_text"]
            }
          }
        ],
        "filter": [
          { "term": { "channel": "email" } },
          { "range": { "timestamp": { "gte": "now-1w" } } }
        ]
      }
    },
    "highlight": {
      "fields": { "body_text": {}, "transcript": {}, "translated_text": {} }
    },
    "sort": [{ "timestamp": { "order": "desc" } }]
  },
  "explanation": "Searching for messages containing 'quarterly earnings' in email channel from the last 7 days."
}
```

**LLM System Prompt** (used by the translation endpoint):

The system prompt instructs the LLM to:
- Accept a natural language search query and an Elasticsearch field schema
- Produce a valid Elasticsearch query DSL body (JSON)
- Map temporal expressions ("last week", "yesterday", "past 3 months") to ES range filters using relative date math (`now-1w`, `now-1d`, etc.)
- Map channel references ("emails", "Teams chats", "calls") to `channel` term filters
- Map participant references to nested `participants` queries
- Map sentiment references to `sentiment` term filters
- Use `multi_match` on text fields (`body_text`, `transcript`, `translated_text`) for content queries
- Always include highlighting on text fields
- Return an `explanation` field summarizing how the query was interpreted
- Never fabricate field names — only use fields from the provided schema

### UI Backend — New Endpoint

| Method | Path | Role | Description |
|---|---|---|---|
| `POST` | `/api/v1/messages/nl-search` | reviewer | Natural language search over messages |

**Request body:**

```python
class NLSearchRequest(BaseModel):
    query: str                           # natural language query
    offset: int = 0
    limit: int = 20
```

**Response:** Standard `MessageSearchResponse` with two extra fields:

```python
class NLSearchResponse(MessageSearchResponse):
    generated_query: dict                # the ES query DSL produced by the LLM
    explanation: str                     # human-readable summary of query interpretation
```

**Backend logic:**
1. Call Agent Runtime `POST /translate-query` with the user's query and the `messages-*` field schema
2. Validate the returned ES query (reject writes, scripts, or unknown indices)
3. Inject `from` and `size` from the request's `offset`/`limit`
4. Execute the query against `messages-*`
5. Parse hits into the standard `ESMessageHit` format
6. Return `NLSearchResponse` with hits + the generated query + explanation

### Frontend Changes

#### Search Mode Toggle

Add a toggle to `MessageSearchForm` that switches between **Keyword** and **Natural Language** search modes:

```
┌──────────────────────────────────────────────────────────────────────┐
│  ┌──────────────┐ ┌──────────────────┐                              │
│  │   Keyword    │ │ Natural Language  │   ← toggle (tabs or switch) │
│  └──────────────┘ └──────────────────┘                              │
│                                                                      │
│  ┌──────────────────────────────────────────────────────┐  ┌──────┐ │
│  │ Show me emails from last week about quarterly earnings│  │Search│ │
│  └──────────────────────────────────────────────────────┘  └──────┘ │
│                                                                      │
│  ┌ Generated query ─────────────────────────────────────────────┐   │
│  │ Searching for messages containing 'quarterly earnings' in    │   │
│  │ email channel from the last 7 days.                          │   │
│  │                                                               │   │
│  │ ▸ View ES query                  (collapsible JSON viewer)   │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  Results (same MessageSearchResults component as keyword search)     │
└──────────────────────────────────────────────────────────────────────┘
```

**Behavior by mode:**

| | Keyword mode (current) | Natural Language mode (new) |
|---|---|---|
| **Input** | KQL / keyword text + filter dropdowns | Free-text natural language question |
| **Filters panel** | Shown (channel, direction, date, etc.) | Hidden (the LLM extracts filters from the query) |
| **API call** | `GET /api/v1/messages/search?q=...` | `POST /api/v1/messages/nl-search` |
| **Extra UI** | — | Explanation banner + collapsible generated query viewer |
| **Placeholder text** | "Search messages..." | "Ask a question, e.g. 'Show me emails about the Q3 report from last month'" |

#### New Frontend Files

```
ui/frontend/src/
├── api/
│   └── messages.ts              # + nlSearch() function
├── hooks/
│   └── useMessages.ts           # + useNLSearch() hook
├── components/
│   └── messages/
│       ├── SearchModeToggle.tsx  # Keyword / Natural Language tab toggle
│       └── NLQueryExplainer.tsx  # Explanation banner + collapsible JSON viewer
└── pages/
    └── MessagesPage.tsx         # Updated to support both modes
```

#### `api/messages.ts` — New function

```typescript
export interface NLSearchRequest {
  query: string;
  offset?: number;
  limit?: number;
}

export interface NLSearchResponse extends MessageSearchResponse {
  generated_query: Record<string, unknown>;
  explanation: string;
}

export async function nlSearchMessages(body: NLSearchRequest): Promise<NLSearchResponse> {
  return apiFetch("/messages/nl-search", {
    method: "POST",
    body: JSON.stringify(body),
  });
}
```

#### `hooks/useMessages.ts` — New hook

```typescript
export function useNLSearch(query: string, offset: number, limit: number) {
  return useQuery({
    queryKey: ["messages", "nl-search", query, offset, limit],
    queryFn: () => nlSearchMessages({ query, offset, limit }),
    enabled: !!query,
  });
}
```

#### `MessagesPage.tsx` — Updated flow

- New state: `searchMode: "keyword" | "nl"` (default `"keyword"`, persisted in URL as `?mode=nl`)
- When `mode=nl`: render a single textarea input (no filter dropdowns), call `useNLSearch`
- When `mode=keyword`: current behavior unchanged
- Both modes render the same `MessageSearchResults` component for results
- In NL mode, show `NLQueryExplainer` above results with the explanation and collapsible generated query

#### `NLQueryExplainer.tsx`

A small component that displays:
- The LLM's `explanation` string in a highlighted info banner
- A collapsible "View generated query" section showing the raw ES query DSL as formatted JSON
- This gives users transparency into how their natural language was interpreted

---

## 8. Pre-built Agents

Shipped as seed data (inserted by migration). Users cannot edit built-in agents but can clone them.

### Comms Reviewer

- **Purpose:** Review flagged communications, draft dispositions with cited evidence.
- **Tools:** `es_search`, `entity_lookup`, `sql_query`
- **Data sources:** `messages-*`, `alerts-*` (ES); `entity`, `alert`, `review` (PG)
- **System prompt:** Reviews the flagged message and surrounding context, identifies policy violations, and produces a structured disposition recommendation with severity, rationale, and evidence citations.
- **Output schema:** `{ severity, disposition, rationale, evidence: [{ source, excerpt }] }`

### Trade Surveillance

- **Purpose:** Correlate trade data with communications to detect suspicious patterns.
- **Tools:** `es_search`, `es_aggregation`, `time_series`, `entity_lookup`
- **Data sources:** `messages-*`, `trades-*` (ES); `entity` (PG)
- **System prompt:** Given a trade or entity, search for related communications and trading activity to identify potential market abuse, insider trading, or front-running.

### Entity Risk Profiler

- **Purpose:** Build behavioral risk profiles by aggregating activity across data sources.
- **Tools:** `es_search`, `es_aggregation`, `entity_lookup`, `time_series`
- **Data sources:** `messages-*`, `alerts-*` (ES); `entity`, `alert` (PG)
- **System prompt:** Given an entity, build a comprehensive risk profile by analyzing communication patterns, alert history, peer relationships, and behavioral trends.

### Anomaly Detector

- **Purpose:** Identify statistical outliers and behavioral deviations.
- **Tools:** `es_aggregation`, `time_series`, `sql_query`
- **Data sources:** `messages-*` (ES); `entity` (PG)
- **System prompt:** Analyze time-series data to detect anomalies — volume spikes, off-hours activity, unusual recipient patterns, frequency changes. Produce ranked list of anomalies with confidence scores.

### Semantic Search

- **Purpose:** RAG-powered natural language search across all indexed data.
- **Tools:** `es_search`, `es_vector_search`
- **Data sources:** `messages-*` (ES)
- **System prompt:** Answer the user's natural language question by searching across all available data. Cite sources with document IDs and timestamps.

---

## 9. Observability & Audit

### Structured Logging

All agent runtime operations use `structlog` with:
- `agent_id`, `run_id`, `step_order` in log context
- Tool call inputs/outputs (with configurable PII redaction)
- Token usage and latency per step

### Metrics (Future)

Expose Prometheus metrics:
- `agent_runs_total` (counter, labels: agent_id, status)
- `agent_run_duration_seconds` (histogram, labels: agent_id)
- `agent_token_usage_total` (counter, labels: agent_id, model)
- `tool_calls_total` (counter, labels: tool_name, agent_id)

### Audit Trail

The `agent.runs` and `agent.run_steps` tables serve as the agent audit trail. Every LLM call, tool invocation, and result is recorded with timestamps and token usage. This satisfies regulatory requirements for explainable AI decisions.

The existing `review.audit_log` table captures when agent-generated dispositions are accepted or modified by human reviewers, maintaining the human-in-the-loop audit chain.

---

## 10. Security

### Data Access Control

- Agents can **only read** data — no write access to ES or PG through tools.
- The SQL tool uses a dedicated `agent_readonly` PostgreSQL role with only SELECT grants on allowed schemas.
- ES tools filter queries to the agent's configured index patterns.
- The runtime validates data source access before every tool invocation.

### Prompt Injection Mitigation

- System prompts are set by supervisors/admins, not end users.
- User input is passed as the `HumanMessage`, never injected into the system prompt.
- Tool outputs are treated as untrusted (LangChain's default behavior).

### Secret Management

- LLM API keys are stored as Kubernetes Secret references (`api_key_secret` column), not plaintext in the database.
- The runtime reads secrets from the mounted volume at startup.

### Rate Limiting

- Per-user rate limits on agent execution (configurable, default 30 runs/hour).
- Global concurrency limit (`AGENTS_MAX_CONCURRENT_RUNS`).
- Per-run token budget (enforced via LiteLLM `max_tokens` setting).

---

## 11. Deployment

### Kubernetes

New manifests in `deploy/k8s/umbrella-agents/`:

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: umbrella-agents
  namespace: umbrella-agents
spec:
  replicas: 2
  template:
    spec:
      containers:
        - name: agents
          image: umbrella-agents:latest
          ports:
            - containerPort: 8001
          env:
            - name: AGENTS_DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: postgresql-credentials
                  key: AGENT_DATABASE_URL
            - name: AGENTS_ES_URL
              value: "http://elasticsearch.umbrella-storage:9200"
          resources:
            requests:
              memory: "512Mi"
              cpu: "250m"
            limits:
              memory: "2Gi"
              cpu: "1000m"
```

- Separate namespace: `umbrella-agents`
- Service: ClusterIP (internal only, accessed by UI backend)
- HPA: scale on CPU/memory (agent execution is CPU/memory-intensive during LLM calls)

### ConfigMap for Built-in Agent Seeds

Pre-built agent configs shipped as a ConfigMap, loaded by the migration or a seed job.

---

## 12. Implementation Phases

### Phase 1a — Database + Agent Runtime Skeleton + NL Search

**Goal:** Schema exists, agent runtime runs with health endpoint, and natural language query translation is available end-to-end.

1. Write migration `V10__agent.sql` — create `agent` schema and all 7 tables
2. Update `deploy/k8s/umbrella-storage/postgresql/migration-job.yaml` ConfigMap
3. Create `agents/` package skeleton:
   - `config.py` (pydantic-settings)
   - `db/engine.py` (async DB engine + session factory)
   - `db/models.py` (SQLAlchemy models for all 7 tables)
   - `es/client.py` (ES client wrapper)
   - `model_router.py` (LiteLLM integration — NL→ES query translation)
   - `routers/health.py` (`GET /health`)
   - `routers/translate.py` (`POST /translate-query` — NL → ES query DSL)
   - `app.py` + `__main__.py`
4. Add `POST /api/v1/messages/nl-search` endpoint to UI backend (proxies to runtime `/translate-query`, validates + executes the generated ES query)
5. Add Pydantic schemas: `NLSearchRequest`, `NLSearchResponse`
6. Tests for query translation and NL search endpoint

**Deliverable:** Working NL search via `curl` / API client. Agent runtime serves health and translation endpoints.

### Phase 1b — Agent Executor, Tools, CRUD

**Goal:** Agents can be created, configured, and executed via API.

1. `executor.py` (LangGraph ReAct agent builder + runner)
2. Tool catalog: `tools/registry.py` + `es_search.py` + `sql_query.py`
3. `callbacks/audit.py` (run_steps logger)
4. `routers/execute.py` (`POST /execute` on runtime)
5. Add UI backend routers: agents CRUD, agent-runs execution proxy, agent-models, agent-tools
6. Add Pydantic schemas for all agent CRUD + execution request/response models
7. Tests for executor, tools, and CRUD endpoints

**Deliverable:** Working agent execution and CRUD via `curl` / API client.

### Phase 2 — Agent Builder UI + Natural Language Search

**Goal:** Users can create and manage agents through the frontend. Natural language search is available on the Messages page.

1. Frontend API client (`api/agents.ts`) and React Query hooks (`hooks/useAgents.ts`)
2. `AgentsPage` — list agents with tabs, create button
3. `AgentEditorPage` — multi-step wizard for creating/editing agents
4. `AgentDetailPage` — view config, run history
5. Tool selector and data source picker components
6. Navigation update (add "Agents" to sidebar)
7. Natural language search on Messages page:
   - `SearchModeToggle` component (Keyword / Natural Language tabs)
   - `NLQueryExplainer` component (explanation banner + collapsible generated query viewer)
   - `nlSearchMessages()` API function and `useNLSearch()` hook
   - Update `MessagesPage` to support both search modes

**Deliverable:** Full CRUD for agents from the UI. Natural language search available on the Messages page.

### Phase 3 — Playground & Streaming

**Goal:** Interactive agent testing with real-time output.

1. SSE streaming from agent runtime → UI backend → frontend
2. `AgentPlaygroundPage` — chat-like interface with streaming output
3. `RunStepInspector` — expandable step trace (tool calls, LLM reasoning)
4. Token usage display and run metadata

**Deliverable:** Users can interactively test agents and inspect their reasoning.

### Phase 4 — Pre-built Agents & Remaining Tools

**Goal:** Ship ready-to-use agents and complete the tool catalog.

1. Implement remaining tools: `es_aggregation`, `es_vector_search`, `entity_lookup`, `time_series`
2. Seed pre-built agents (Comms Reviewer, Trade Surveillance, Entity Risk Profiler, Anomaly Detector, Semantic Search)
3. Clone functionality (clone built-in agent → custom agent)
4. Agent run history page with filtering and export

**Deliverable:** Production-ready agent system with out-of-the-box agents.

### Phase 5 — Hardening & Observability

**Goal:** Production-grade security, monitoring, and performance.

1. Rate limiting and concurrency controls
2. PII redaction in logs and run_steps
3. Prometheus metrics endpoint
4. K8s deployment manifests, HPA, resource limits
5. Load testing and performance tuning
6. Documentation (user-facing agent builder guide)

**Deliverable:** Production deployment with monitoring and security controls.
