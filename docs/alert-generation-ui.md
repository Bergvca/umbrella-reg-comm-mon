# Alert Generation — Implementation Plan

## Overview

Alert generation has two modes:

1. **On-ingest (real-time):** As messages are indexed into Elasticsearch, an ES percolator evaluates them against registered rule queries and creates alerts immediately. This is the primary, always-on path.
2. **On-demand (batch):** A "Generate Alerts" button on the Alerts page lets supervisors trigger a batch run — scoped by policy/risk-model selection and a KQL query filter. The default filter targets everything ingested since the last generation run. This handles backfills, new rules, and ad-hoc investigations.

The design accommodates future scheduled generation.

## Current State

- **Alert creation** happens outside the UI backend — the ingestion pipeline (connectors → processors → ingestion service) writes alerts to `alert.alerts`.
- **The UI backend** is a pure read/update API: it lists alerts, fetches details (joining ES documents), and updates statuses. It has no background task infrastructure.
- **Policies and risk models** are fully modeled: `policy.risk_models` → `policy.policies` → `policy.rules` (each rule holds a KQL expression and severity).
- **Alert table** has a unique constraint on `(rule_id, es_document_id)`, so re-running rules against already-alerted documents is naturally idempotent.

## Mode 1: Real-Time Alerting via ES Percolator

### How Percolate Works

Elasticsearch's [percolate query](https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-percolate-query.html) inverts the normal search model: instead of searching documents against a query, you register queries (rules) in a special index and then percolate documents against them. ES returns which registered queries match a given document.

### Design

**Percolator index: `umbrella-alert-rules`**

Each document in this index represents one active rule:

```json
{
  "rule_id": "<uuid>",
  "policy_id": "<uuid>",
  "risk_model_id": "<uuid>",
  "severity": "high",
  "query": {
    "query_string": { "query": "<KQL expression from policy.rules.kql>" }
  }
}
```

The index mapping must include a `query` field of type `percolator` and mirror the field mappings of the main message index (so ES can analyze the percolate candidate against the registered queries).

**Sync: rules → percolator index**

When rules are created, updated, activated, or deactivated via the policy API, the percolator index must be kept in sync:

- **Rule created/activated** → upsert document into `umbrella-alert-rules` (doc ID = rule UUID)
- **Rule updated** → re-index the document with the new KQL
- **Rule deactivated/deleted** → delete from `umbrella-alert-rules`

This sync happens in the existing policy routers (rules CRUD endpoints) as a side-effect, using the ES client already available in the UI backend. A full resync endpoint (`POST /api/v1/alert-generation/sync-rules`) is also provided for bootstrap/recovery.

**Percolation at ingest time**

In the ingestion service (`ingestion-api/umbrella_ingestion/service.py`), after a normalized message is indexed into ES:

1. Take the indexed document and run a `percolate` query against `umbrella-alert-rules`
2. For each matching rule returned:
   - Insert into `alert.alerts` (with `ON CONFLICT (rule_id, es_document_id) DO NOTHING`)
3. Log matches via structlog

This adds a single ES query per ingested message. The percolator is optimized for this pattern and handles thousands of registered queries efficiently.

**Failure handling:** If percolation fails (ES timeout, transient error), log the error and continue — the message is already indexed. The batch generation mode serves as a safety net to catch any missed alerts.

### Changes Required

| Component | Change |
|-----------|--------|
| ES index mapping | Create `umbrella-alert-rules` index with `percolator` field type + mirrored message mappings |
| Policy routers (`rules` CRUD) | Add percolator upsert/delete as side-effect on rule create/update/delete/activate |
| New endpoint | `POST /api/v1/alert-generation/sync-rules` — full resync of all active rules to percolator index |
| Ingestion service | After ES index, run percolate query → insert alerts |
| K8s / config | Ingestion service needs `ALERT_DATABASE_URL` for PG writes + percolator index name config |

---

## Mode 2: On-Demand Batch Generation

### Architecture Decision: Where Does Batch Generation Run?

Batch generation requires executing KQL queries against Elasticsearch for every active rule in the selected scope, filtered by a user-provided KQL query. This is potentially long-running and should **not** block an HTTP request.

**Approach: async background worker in the UI backend.**

Add a lightweight task runner (using `asyncio.create_task` or a small job queue) to the UI backend. The API endpoint accepts the generation request, enqueues a job, and returns a job ID immediately. The frontend can poll for status.

This keeps the system simple (no new service to deploy) while remaining non-blocking. If generation workloads grow, this can later be extracted into a dedicated service or moved behind a task queue (e.g. Celery, ARQ).

### Alternative considered

A separate microservice or Kafka-based approach. Rejected for now — the UI backend already has ES and PG connections, and adding a new service for a single admin action is premature.

## Data Model Changes

### New table: `alert.generation_jobs`

```sql
CREATE TABLE alert.generation_jobs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scope_type      TEXT NOT NULL CHECK (scope_type IN ('all', 'policies', 'risk_models')),
    scope_ids       UUID[],                        -- NULL when scope_type = 'all'
    query_kql       TEXT,                          -- additional KQL filter applied to ES searches
                                                   -- NULL = use default (since last completed run)
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    alerts_created  INTEGER DEFAULT 0,
    rules_evaluated INTEGER DEFAULT 0,
    documents_scanned BIGINT DEFAULT 0,
    error_message   TEXT,
    created_by      UUID NOT NULL REFERENCES iam.users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,

    -- Future: scheduling fields (initially NULL / unused)
    schedule_cron   TEXT,                          -- e.g. '0 6 * * 1-5'
    schedule_active BOOLEAN DEFAULT FALSE
);
```

This lives in a new migration file (V8).

### Default KQL query: "since last run"

When `query_kql` is NULL (the default), the generation engine resolves it at runtime:

1. Find the most recent `completed` job in `generation_jobs` (ordered by `completed_at DESC`)
2. If found, use: `@timestamp >= "<completed_at ISO>"` — this targets all messages ingested after the last successful run
3. If no previous run exists (first ever run), use `*` (match all)

This ensures batch runs are incremental by default — only scanning new messages — while allowing users to override with a custom KQL for backfills or targeted investigations (e.g. `channel:email AND @timestamp >= "2025-01-01"`).

## Backend Changes

### 1. ORM model — `db/models/alert.py`

Add `GenerationJob` mapped to `alert.generation_jobs`.

### 2. Schemas — `schemas/alert.py`

```
GenerationJobCreate:
    scope_type: Literal['all', 'policies', 'risk_models']
    scope_ids: list[UUID] | None = None   # required when scope_type != 'all'
    query_kql: str | None = None          # NULL = default "since last run"

GenerationJobOut:
    id, scope_type, scope_ids, query_kql, query_kql_resolved,
    status, alerts_created, rules_evaluated, documents_scanned,
    error_message, created_by, created_at, started_at, completed_at
```

`query_kql_resolved` is a computed read-only field showing the actual KQL that was/will be used (useful when the input was NULL and the default was applied).

### 3. Generation engine — `services/alert_generator.py` (new)

Core logic, run inside a background task:

```
async def run_generation_job(job_id: UUID):
    1. Load the job row, set status = 'running', started_at = now()
    2. Resolve the KQL query:
       - If query_kql is set → use it as-is
       - If query_kql is NULL → look up last completed job's completed_at
         → build '@timestamp >= "<iso>"' (or '*' if no prior job)
       - Store the resolved query back to the row (for auditability)
    3. Resolve scope → list of active rules:
       - 'all':          all active rules from active policies from active risk models
       - 'policies':     active rules where policy_id IN scope_ids
       - 'risk_models':  active rules where policy.risk_model_id IN scope_ids
    4. For each rule:
       a. Build ES query: bool { must: [rule.kql, resolved_query_kql] }
          — the rule KQL selects matching content, the job KQL scopes the time/data range
       b. Use scroll/search_after to iterate all matching ES documents
       c. For each match not already in alert.alerts (ON CONFLICT DO NOTHING):
          - INSERT into alert.alerts
          - Increment alerts_created counter
       d. Increment rules_evaluated, accumulate documents_scanned
    5. Set status = 'completed', completed_at = now()
    6. On exception: set status = 'failed', error_message = str(error)
```

### 4. Router — `routers/alert_generation.py` (new)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/v1/alert-generation/jobs` | supervisor | Create + start a generation job |
| `GET` | `/api/v1/alert-generation/jobs` | supervisor | List recent jobs (last 50, newest first) |
| `GET` | `/api/v1/alert-generation/jobs/{id}` | supervisor | Get job status + progress |
| `GET` | `/api/v1/alert-generation/default-query` | supervisor | Returns the default KQL that would be used (based on last completed job) |
| `POST` | `/api/v1/alert-generation/sync-rules` | admin | Full resync of all active rules to the percolator index |

The POST handler:
1. Validates `scope_ids` exist (policies or risk models) if `scope_type != 'all'`
2. Inserts `generation_jobs` row
3. Fires `asyncio.create_task(run_generation_job(job_id))`
4. Returns the job immediately with `status: 'pending'`

### 5. Register router in `app.py`

Add the new router with the `/api/v1/alert-generation` prefix.

## Frontend Changes

### 1. API layer — `api/alert-generation.ts` (new)

```ts
createGenerationJob(body: GenerationJobCreate): Promise<GenerationJobOut>
listGenerationJobs(): Promise<GenerationJobOut[]>
getGenerationJob(id: string): Promise<GenerationJobOut>
```

### 2. Types — `lib/types.ts`

```ts
interface GenerationJobCreate {
  scope_type: 'all' | 'policies' | 'risk_models'
  scope_ids?: string[]
  query_kql?: string | null  // null = default "since last run"
}

interface GenerationJobOut {
  id: string
  scope_type: 'all' | 'policies' | 'risk_models'
  scope_ids: string[] | null
  query_kql: string | null
  query_kql_resolved: string        // the actual KQL used (after default resolution)
  status: 'pending' | 'running' | 'completed' | 'failed'
  alerts_created: number
  rules_evaluated: number
  documents_scanned: number
  error_message: string | null
  created_by: string
  created_at: string
  started_at: string | null
  completed_at: string | null
}
```

### 3. Hook — `hooks/useAlertGeneration.ts` (new)

- `useCreateGenerationJob()` — mutation, invalidates `["generation-jobs"]` on success
- `useGenerationJobs()` — query for listing recent jobs
- `useGenerationJob(id)` — query with `refetchInterval: 2000` while status is `pending` or `running` (auto-polls for progress)

### 4. Dialog component — `components/alerts/GenerateAlertsDialog.tsx` (new)

**Trigger:** A `<Button variant="outline">` with a Play/Zap icon + "Generate Alerts" text, placed in the `AlertsPage` header next to the existing `ExportButton`. Visible only to supervisors+.

**Dialog content — three steps:**

**Step 1 — Scope selection (radio group):**
- "All active policies" — no further selection needed
- "Selected policies" — reveals a multi-select checklist of policies (fetched via `usePolicies()`)
- "Selected risk models" — reveals a multi-select checklist of risk models (fetched via `useRiskModels()`)

Policies and risk models are shown with name + active/inactive badge. Only active items are pre-checked / selectable.

**Step 2 — Query filter:**
- A KQL input field (monospace `Textarea`, matching the existing `RuleForm` KQL input style)
- Pre-populated with the default: `@timestamp >= "<last completed job timestamp>"` (fetched from the API) or `*` if no prior run
- Label: "Message filter (KQL)" with helper text: "Controls which indexed messages are evaluated. Default: messages ingested since the last generation run."
- Users can clear and type a custom KQL (e.g. `channel:email AND @timestamp >= "2025-06-01"`) or leave the default

**Step 3 — Confirmation:**
Summary line: "This will evaluate X rules across Y policies."
Shows the resolved KQL query that will be used.
- "Generate" primary button + "Cancel" ghost button.

**After submit:**
- Dialog stays open, shows a progress view:
  - Status badge (running / completed / failed)
  - `rules_evaluated` / total rules progress
  - `alerts_created` counter
  - Polls via `useGenerationJob(id)` with 2s interval
- On completion: success toast via `sonner`, "Close" button, alert list auto-refreshes (invalidate `["alerts"]` query).

### 5. Update `AlertsPage.tsx`

Add `<GenerateAlertsDialog />` in the page header, gated behind `canEdit` (supervisor+ role check, matching the existing `ExportButton` pattern).

## Future: Scheduling

The `generation_jobs` table already includes `schedule_cron` and `schedule_active` columns. When scheduling is implemented:

1. **Backend**: Add a scheduler (e.g. APScheduler or a simple `asyncio` loop) that reads active schedules from `generation_jobs` where `schedule_active = true`, evaluates cron expressions, and spawns jobs.
2. **API**: Add `PATCH /api/v1/alert-generation/jobs/{id}/schedule` to set/update/deactivate a schedule.
3. **Frontend**: Add a "Schedule" tab or toggle in the dialog showing active schedules, with cron expression input (or a friendly frequency picker).

The schema and job-tracking infrastructure built in this phase carries forward unchanged.

## Migration File

`infrastructure/postgresql/migrations/V8__alert_generation_jobs.sql`

## Implementation Order

### Phase 1: Percolator (real-time alerting on ingest)
1. **ES index setup** — create `umbrella-alert-rules` index with percolator mapping mirroring the message index fields
2. **Rule sync** — add percolator upsert/delete side-effects to existing rule CRUD in policy routers
3. **Sync endpoint** — `POST /api/v1/alert-generation/sync-rules` for initial bootstrap / recovery
4. **Ingestion service changes** — after indexing a message, percolate against `umbrella-alert-rules`, insert matching alerts into PG
5. **Test** — ingest a message that matches a rule, verify alert is created

### Phase 2: Batch generation (on-demand via UI)
6. **Migration** — create `alert.generation_jobs` table (V8)
7. **Backend model + schema** — ORM model and Pydantic schemas (including `query_kql`)
8. **Generation engine** — core `run_generation_job` logic with KQL resolution, ES queries, and alert insertion
9. **Router** — API endpoints for creating/listing/getting jobs + default-query helper
10. **Frontend types + API + hook** — data layer
11. **Dialog component** — UI with scope selection, KQL filter, confirmation, and progress
12. **Wire into AlertsPage** — add button, test end-to-end

### Phase 3 (future): Scheduling
13. Cron evaluator + schedule management API + UI

## Open Questions

- **Percolator field mappings**: The `umbrella-alert-rules` index needs field mappings that mirror the message index. Need to decide: manually duplicate the mapping, or use an index template/component template shared between message and percolator indexes?
- **Concurrency**: Should we prevent multiple batch jobs from running simultaneously? A simple check (reject if any job is `pending` or `running`) would prevent accidental duplicate runs.
- **Notifications**: Should the generating user receive an in-app notification when a long-running job completes? Currently the dialog polls, but if they navigate away they lose visibility.
- **KQL validation**: Should the API validate the user-provided KQL before starting the job? Could do a lightweight `_validate/query` call to ES to catch syntax errors early.

---

## Detailed Implementation Spec

### Key Discovery: Ingestion Service ↔ ES

The ingestion service does **not** talk to ES directly — Logstash consumes from Kafka and indexes. For the percolator, we use the ES percolate API with **inline documents** (the doc doesn't need to be in the ES index yet). This means adding an ES client + PG alert writes to the ingestion service.

### Files to Create

| File | Purpose |
|------|---------|
| `infrastructure/elasticsearch/umbrella-alert-rules-mapping.json` | Percolator index mapping |
| `infrastructure/postgresql/migrations/V8__alert_generation_jobs.sql` | generation_jobs table |
| `ui/backend/umbrella_ui/es/percolator.py` | Percolator index helpers (upsert/delete rule, ensure index) |
| `ui/backend/umbrella_ui/routers/alert_generation.py` | Sync-rules + job CRUD endpoints |
| `ui/backend/umbrella_ui/services/__init__.py` | Package init |
| `ui/backend/umbrella_ui/services/alert_generator.py` | Batch generation engine |
| `ingestion-api/umbrella_ingestion/percolator.py` | Ingest-time percolation + alert PG insert |
| `ui/frontend/src/api/alert-generation.ts` | Frontend API layer |
| `ui/frontend/src/hooks/useAlertGeneration.ts` | TanStack Query hooks |
| `ui/frontend/src/components/alerts/GenerateAlertsDialog.tsx` | Multi-step dialog component |

### Files to Modify

| File | Change |
|------|--------|
| `ui/backend/umbrella_ui/routers/policies.py` | Add ES dep + percolator side-effects to `create_rule`, `update_rule`, `delete_rule` |
| `ui/backend/umbrella_ui/app.py` | Import + register `alert_generation_router` |
| `ui/backend/umbrella_ui/db/models/alert.py` | Add `GenerationJob` ORM model |
| `ui/backend/umbrella_ui/schemas/alert.py` | Add `GenerationJobCreate` / `GenerationJobOut` |
| `ingestion-api/umbrella_ingestion/config.py` | Add `ElasticsearchConfig` + `AlertDBConfig` |
| `ingestion-api/umbrella_ingestion/service.py` | Wire `AlertPercolator` lifecycle + call in `_dual_write` |
| `ingestion-api/pyproject.toml` | Add `elasticsearch[async]>=8.0,<9.0` |
| `ui/frontend/src/lib/types.ts` | Add generation job types |
| `ui/frontend/src/pages/AlertsPage.tsx` | Add `GenerateAlertsDialog` to header |

---

### Phase 1 Detail: Percolator

#### 1a. ES Index Mapping (`infrastructure/elasticsearch/umbrella-alert-rules-mapping.json`)

```json
{
  "mappings": {
    "properties": {
      "query":          { "type": "percolator" },
      "rule_id":        { "type": "keyword" },
      "rule_name":      { "type": "keyword" },
      "policy_id":      { "type": "keyword" },
      "risk_model_id":  { "type": "keyword" },
      "severity":       { "type": "keyword" },
      "message_id":     { "type": "keyword" },
      "channel":        { "type": "keyword" },
      "direction":      { "type": "keyword" },
      "timestamp":      { "type": "date" },
      "body_text":      { "type": "text", "analyzer": "standard" },
      "participants":   {
        "type": "nested",
        "properties": {
          "id":   { "type": "keyword" },
          "name": { "type": "text" },
          "role": { "type": "keyword" }
        }
      },
      "metadata": {
        "properties": {
          "subject": { "type": "text" }
        }
      }
    }
  }
}
```

#### 1b. Percolator Helper (`ui/backend/umbrella_ui/es/percolator.py`)

```python
PERCOLATOR_INDEX = "umbrella-alert-rules"

async def ensure_percolator_index(es: AsyncElasticsearch) -> None:
    """PUT index with mapping if doesn't exist (ignore 400)."""

def _rule_to_percolator_doc(rule_id, rule_name, policy_id, risk_model_id, kql, severity) -> dict:
    """Build percolator doc. query = query_string wrapping KQL."""
    return {
        "rule_id": str(rule_id), "rule_name": rule_name,
        "policy_id": str(policy_id), "risk_model_id": str(risk_model_id),
        "severity": severity,
        "query": {"query_string": {"query": kql, "default_field": "body_text"}},
    }

async def upsert_rule(es, rule_id, rule_name, policy_id, risk_model_id, kql, severity) -> None:
    """es.index(index=PERCOLATOR_INDEX, id=str(rule_id), document=doc)"""

async def delete_rule(es, rule_id) -> None:
    """es.delete(index=PERCOLATOR_INDEX, id=str(rule_id)), ignore 404"""
```

#### 1c. Policy Router Side-Effects (`ui/backend/umbrella_ui/routers/policies.py`)

Add `es: Annotated[AsyncElasticsearch, Depends(get_es)]` to `create_rule` (line 187), `update_rule` (line 226), `delete_rule` (line 254).

After each commit, wrap percolator calls in try/except (never fail the CRUD):

- **create_rule** (after line 207): fetch policy's risk_model_id, `upsert_rule` if rule+policy active
- **update_rule** (after line 250): if rule+policy active → `upsert_rule`, else → `delete_rule`
- **delete_rule** (after line 265): `delete_rule` (soft-delete sets is_active=False)

#### 1d. Alert Generation Router — sync-rules (`ui/backend/umbrella_ui/routers/alert_generation.py`)

```python
router = APIRouter(prefix="/api/v1/alert-generation", tags=["alert-generation"])

@router.post("/sync-rules")
async def sync_rules(es, session, _user=require_role("admin")):
    """Ensure index exists, query all active rules (join Policy+RiskModel), upsert each."""
    # Returns {upserted: N, errors: N}
```

Register in `app.py` after export_router.

#### 1e. Ingestion Service Config (`ingestion-api/umbrella_ingestion/config.py`)

```python
class ElasticsearchConfig(BaseSettings):
    model_config = {"env_prefix": "ES_"}
    url: str = "http://localhost:9200"
    percolator_index: str = "umbrella-alert-rules"
    request_timeout: int = 10

class AlertDBConfig(BaseSettings):
    model_config = {"env_prefix": "ALERT_DB_"}
    dsn: str | None = None  # if None, percolation disabled
```

Add as `es` and `alert_db` fields on `IngestionConfig`.

#### 1f. AlertPercolator (`ingestion-api/umbrella_ingestion/percolator.py`)

Mirrors `EntityResolver` lifecycle pattern:

```python
class AlertPercolator:
    def __init__(self, es_config, alert_db_config): ...
    async def start(self):    # creates AsyncElasticsearch + asyncpg.Pool
    async def stop(self):     # closes both

    async def percolate(self, message_id, es_index, document, document_ts) -> int:
        # 1. es.search(index=percolator_index, body={query: {percolate: {field: "query", document: doc}}})
        # 2. For each hit: INSERT INTO alert.alerts ... ON CONFLICT DO NOTHING
        # 3. Return count of alerts created
        # Fail-open: exceptions logged and swallowed
```

SQL: `INSERT INTO alert.alerts (name, rule_id, es_index, es_document_id, es_document_ts, severity) VALUES (...) ON CONFLICT (rule_id, es_document_id) DO NOTHING`

#### 1g. Wire into Service (`ingestion-api/umbrella_ingestion/service.py`)

- `__init__`: create `AlertPercolator` (like EntityResolver, lines 33-38)
- `run()`: add `start()/stop()` (after resolver, lines 98-99 / 113-114)
- `_dual_write()`: after S3 write (line 181), build doc dict from normalized fields, call `self._percolator.percolate(...)`:

```python
if self._percolator:
    doc = {
        "message_id": normalized.message_id,
        "channel": normalized.channel.value,
        "direction": normalized.direction.value,
        "timestamp": normalized.timestamp.isoformat(),
        "body_text": normalized.body_text,
        "participants": [{"id": p.id, "name": p.name, "role": p.role} for p in normalized.participants],
        "metadata": normalized.metadata,
    }
    es_index = f"messages-{normalized.timestamp:%Y.%m}"
    await self._percolator.percolate(normalized.message_id, es_index, doc, normalized.timestamp)
```

#### 1h. Add Dependency (`ingestion-api/pyproject.toml`)

Add `"elasticsearch[async]>=8.0,<9.0"` to dependencies.

---

### Phase 2 Detail: Batch Generation

#### 2a. Migration (`infrastructure/postgresql/migrations/V8__alert_generation_jobs.sql`)

```sql
CREATE TABLE alert.generation_jobs (
    id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    scope_type        TEXT        NOT NULL CHECK (scope_type IN ('all', 'policies', 'risk_models')),
    scope_ids         UUID[],
    query_kql         TEXT,
    query_kql_resolved TEXT,
    status            TEXT        NOT NULL DEFAULT 'pending'
                                  CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    alerts_created    INTEGER     NOT NULL DEFAULT 0,
    rules_evaluated   INTEGER     NOT NULL DEFAULT 0,
    documents_scanned BIGINT      NOT NULL DEFAULT 0,
    error_message     TEXT,
    created_by        UUID        NOT NULL REFERENCES iam.users(id),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at        TIMESTAMPTZ,
    completed_at      TIMESTAMPTZ,
    schedule_cron     TEXT,
    schedule_active   BOOLEAN     NOT NULL DEFAULT false
);

CREATE INDEX ON alert.generation_jobs (created_at DESC);
CREATE INDEX ON alert.generation_jobs (status);
GRANT SELECT, INSERT, UPDATE ON alert.generation_jobs TO alert_rw;
```

#### 2b. ORM Model (`ui/backend/umbrella_ui/db/models/alert.py`)

Add `GenerationJob` after `Alert`. Uses `ARRAY(UUID(as_uuid=True))` for `scope_ids`. Same pattern as existing `Alert` class.

#### 2c. Schemas (`ui/backend/umbrella_ui/schemas/alert.py`)

```python
class GenerationJobCreate(BaseModel):
    scope_type: Literal["all", "policies", "risk_models"]
    scope_ids: list[UUID] | None = None
    query_kql: str | None = None

    @model_validator(mode="after")
    def check_scope_ids(self): ...  # required when scope_type != 'all'

class GenerationJobOut(BaseModel):
    model_config = {"from_attributes": True}
    # all columns from GenerationJob
```

#### 2d. Generation Engine (`ui/backend/umbrella_ui/services/alert_generator.py`)

```python
async def run_generation_job(job_id, alert_session_factory, policy_session_factory, es):
    # 1. Load job → status='running', started_at=now()
    # 2. Resolve KQL (null → '@timestamp >= "<last completed>"' or '*')
    # 3. Resolve scope → list of active rules
    # 4. For each rule:
    #    - ES query: bool.must[query_string(rule.kql), query_string(resolved_kql)]
    #    - PIT + search_after pagination over messages-*
    #    - pg_insert(Alert).on_conflict_do_nothing() for each hit
    #    - Update progress counters periodically
    # 5. status='completed' or 'failed'
```

Uses `sqlalchemy.dialects.postgresql.insert` with `.on_conflict_do_nothing()` for idempotent inserts. Receives `async_sessionmaker` factories (not sessions) since it outlives the request.

#### 2e. Job Endpoints (added to `alert_generation.py` router)

- `GET /default-query` → `{default_kql: "@timestamp >= ..." | "*"}`
- `GET /jobs` → list[GenerationJobOut] (last 50)
- `GET /jobs/{id}` → GenerationJobOut
- `POST /jobs` → 202 + GenerationJobOut
  - Concurrency guard: reject 409 if pending/running job exists
  - `asyncio.create_task(run_generation_job(...))` using `request.app.state.db` session factories

#### 2f. Frontend Types (`ui/frontend/src/lib/types.ts`)

Add `GenerationScopeType`, `GenerationJobStatus`, `GenerationJobCreate`, `GenerationJobOut` interfaces.

#### 2g. Frontend API (`ui/frontend/src/api/alert-generation.ts`)

`getDefaultQuery()`, `createGenerationJob(body)`, `listGenerationJobs()`, `getGenerationJob(id)` — all using `apiFetch` pattern.

#### 2h. Frontend Hooks (`ui/frontend/src/hooks/useAlertGeneration.ts`)

- `useDefaultQuery()` — queryKey: `["generation-jobs", "default-query"]`
- `useGenerationJobs()` — queryKey: `["generation-jobs", "list"]`
- `useGenerationJob(id)` — queryKey: `["generation-jobs", id]`, `refetchInterval: 2000` while pending/running
- `useCreateGenerationJob()` — mutation, invalidates `["generation-jobs"]`

#### 2i. Dialog Component (`ui/frontend/src/components/alerts/GenerateAlertsDialog.tsx`)

Multi-step dialog with `useState<Step>` controlling: `"scope"` → `"query"` → `"confirm"` → `"progress"`.

- **Trigger**: `<Button variant="outline" size="sm">` with Zap icon
- **Scope step**: radio group + conditional multi-select checklist (policies or risk models)
- **Query step**: monospace Textarea, pre-populated from `useDefaultQuery()`
- **Confirm step**: summary + "Generate" button
- **Progress step**: polls `useGenerationJob(id)`, shows status badge + counters, toast on completion

#### 2j. AlertsPage (`ui/frontend/src/pages/AlertsPage.tsx`)

Replace standalone ExportButton with `<div className="flex items-center gap-2">` containing both `<GenerateAlertsDialog />` and `<ExportButton />`, inside existing `isSupervisor` guard.
