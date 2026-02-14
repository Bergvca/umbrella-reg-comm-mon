# UI Layer — Implementation Plan

## 1. Overview

The UI layer is the compliance officer's window into the Umbrella platform. It provides an API backend and a single-page application for reviewing alerts, searching communications, managing review queues, configuring policies, and maintaining a full audit trail.

The UI layer sits at the end of the data pipeline and reads from two stores:

- **Elasticsearch** — full-text search over `messages-*` and `alerts-*` indices (communications, enrichments, compliance alerts)
- **PostgreSQL** — operational state across four schemas: `iam` (users/RBAC), `policy` (risk models, rules), `alert` (alert records), `review` (queues, decisions, audit)

```
┌──────────────────────────────────────────────────────────────────────┐
│                            UI LAYER                                  │
│                                                                      │
│  ┌──────────────────────┐            ┌───────────────────────────┐   │
│  │   UI Backend (API)   │◄──────────►│    Frontend (SPA)         │   │
│  │                      │    REST    │                           │   │
│  │  FastAPI + SQLAlchemy │            │  React + TypeScript       │   │
│  │  Python 3.13         │            │  Vite + TanStack Query    │   │
│  └──────┬───────┬───────┘            └───────────────────────────┘   │
│         │       │                                                    │
│         ▼       ▼                                                    │
│    PostgreSQL  Elasticsearch                                         │
│    (4 schemas) (messages-*, alerts-*)                                │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 2. Technology Choices

### UI Backend

| Concern | Choice | Rationale |
|---|---|---|
| Framework | **FastAPI** | Already used in connector-framework (`fastapi>=0.115`); async-native, OpenAPI auto-generation |
| ORM | **SQLAlchemy 2.0** (async) | De-facto Python ORM; async support via `asyncpg`; Pydantic v2 integration |
| DB driver | **asyncpg** | Fastest async PostgreSQL driver; pairs with SQLAlchemy async engine |
| ES client | **elasticsearch[async] 9.x** | Official async client matching our ES 9.3.0 cluster |
| Auth | **python-jose** (JWT) + **passlib[bcrypt]** | JWT tokens with bcrypt password hashing; OIDC/SSO in Phase 2 |
| Logging | **structlog** | Project convention — structured logging everywhere |
| Settings | **pydantic-settings** | Project convention — env var config with `UMBRELLA_UI_` prefix |
| Build | **Hatchling** | Project convention — same build backend as all other packages |
| Testing | **pytest + httpx** | `pytest-asyncio` auto mode; `httpx.AsyncClient` for API tests |

### Frontend

| Concern | Choice | Rationale |
|---|---|---|
| Framework | **React 19** + **TypeScript 5** | Specified in PLAN.md; industry standard for SPAs |
| Build | **Vite** | Fast HMR, ESBuild bundling, simple config |
| Routing | **React Router v7** | Standard SPA routing |
| Data fetching | **TanStack Query v5** | Declarative server state, caching, background refetch |
| UI components | **shadcn/ui** + **Tailwind CSS v4** | Copy-paste components built on Radix primitives; full control, no vendor lock-in |
| Tables | **TanStack Table v8** | Headless, supports sorting/filtering/pagination/column resizing |
| Forms | **React Hook Form** + **Zod** | Performant forms; Zod schemas mirror backend Pydantic models |
| State | **Zustand** | Lightweight global state for UI preferences and auth context |
| Charts | **Recharts** | Simple, composable charts built on D3 for dashboard metrics |
| Testing | **Vitest** + **Testing Library** | Fast, Vite-native unit tests; React Testing Library for component tests |

---

## 3. Package Structure

### Backend (`ui/backend/`)

```
ui/backend/
├── pyproject.toml
├── Dockerfile
├── umbrella_ui/
│   ├── __init__.py
│   ├── __main__.py              # uvicorn entry point
│   ├── app.py                   # FastAPI app factory
│   ├── config.py                # pydantic-settings (UMBRELLA_UI_ prefix)
│   ├── deps.py                  # FastAPI dependency injection (DB sessions, ES client, current_user)
│   │
│   ├── db/
│   │   ├── __init__.py
│   │   ├── engine.py            # async SQLAlchemy engine + sessionmaker
│   │   └── models/              # SQLAlchemy ORM models (mirror PG schema)
│   │       ├── __init__.py
│   │       ├── iam.py           # User, Role, Group, UserGroup, GroupRole
│   │       ├── policy.py        # RiskModel, Policy, Rule, GroupPolicy
│   │       ├── alert.py         # Alert
│   │       └── review.py        # Queue, QueueBatch, QueueItem, DecisionStatus, Decision, AuditLog
│   │
│   ├── es/
│   │   ├── __init__.py
│   │   ├── client.py            # async ES client wrapper
│   │   ├── queries.py           # reusable ES query builders (messages, alerts, aggregations)
│   │   └── models.py            # Pydantic response models for ES documents
│   │
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── jwt.py               # JWT token creation/validation
│   │   ├── password.py          # bcrypt hashing/verification
│   │   ├── rbac.py              # role-checking dependencies (require_role("admin"), etc.)
│   │   └── schemas.py           # LoginRequest, TokenResponse, etc.
│   │
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth.py              # POST /auth/login, POST /auth/refresh, GET /auth/me
│   │   ├── users.py             # CRUD /users, /users/{id}/groups
│   │   ├── groups.py            # CRUD /groups, /groups/{id}/roles, /groups/{id}/policies
│   │   ├── policies.py          # CRUD /policies, /policies/{id}/rules
│   │   ├── risk_models.py       # CRUD /risk-models
│   │   ├── alerts.py            # GET /alerts (ES+PG join), PATCH /alerts/{id}/status
│   │   ├── messages.py          # GET /messages/search (ES), GET /messages/{id}
│   │   ├── queues.py            # CRUD /queues, /queues/{id}/batches, batch assignment
│   │   ├── decisions.py         # POST /decisions, GET /alerts/{id}/decisions
│   │   ├── audit.py             # GET /audit-log (read-only)
│   │   └── export.py            # GET /export/alerts, /export/messages (CSV/JSON)
│   │
│   └── schemas/                 # Pydantic request/response schemas (separate from DB models)
│       ├── __init__.py
│       ├── common.py            # PaginatedResponse, SortParams, etc.
│       ├── iam.py
│       ├── policy.py
│       ├── alert.py
│       ├── review.py
│       ├── message.py           # ES message search request/response
│       └── export.py
│
└── tests/
    ├── conftest.py              # fixtures: test DB, ES mock, auth headers
    ├── test_auth.py
    ├── test_users.py
    ├── test_alerts.py
    ├── test_messages.py
    ├── test_queues.py
    ├── test_decisions.py
    └── test_policies.py
```

### Frontend (`ui/frontend/`)

```
ui/frontend/
├── package.json
├── tsconfig.json
├── vite.config.ts
├── Dockerfile
├── index.html
├── src/
│   ├── main.tsx                 # React root + providers
│   ├── App.tsx                  # Top-level routes
│   ├── api/
│   │   ├── client.ts            # axios/fetch wrapper with JWT interceptor
│   │   ├── auth.ts              # login, refresh, me
│   │   ├── alerts.ts            # alert queries and mutations
│   │   ├── messages.ts          # message search
│   │   ├── queues.ts            # queue/batch management
│   │   ├── decisions.ts         # decision submission
│   │   ├── policies.ts          # policy/rule CRUD
│   │   └── users.ts             # user/group management
│   │
│   ├── hooks/                   # TanStack Query hooks wrapping api/
│   │   ├── useAlerts.ts
│   │   ├── useMessages.ts
│   │   ├── useQueues.ts
│   │   ├── useAuth.ts
│   │   └── ...
│   │
│   ├── stores/
│   │   └── auth.ts              # Zustand store (token, user, role)
│   │
│   ├── components/
│   │   ├── ui/                  # shadcn/ui primitives (Button, Dialog, Input, etc.)
│   │   ├── layout/
│   │   │   ├── AppShell.tsx     # sidebar + header + main content
│   │   │   ├── Sidebar.tsx      # nav links by role
│   │   │   └── Header.tsx       # user menu, notifications
│   │   ├── alerts/
│   │   │   ├── AlertTable.tsx   # sortable/filterable alert list
│   │   │   ├── AlertDetail.tsx  # single alert + linked ES message
│   │   │   ├── AlertFilters.tsx # severity, status, channel, date range
│   │   │   └── DecisionForm.tsx # submit decision + comment
│   │   ├── messages/
│   │   │   ├── MessageSearch.tsx # full-text search with filters
│   │   │   ├── MessageDetail.tsx # message body, participants, attachments
│   │   │   └── AudioPlayer.tsx  # audio playback with synchronized transcript
│   │   ├── queues/
│   │   │   ├── QueueList.tsx
│   │   │   ├── BatchView.tsx    # reviewer's assigned batch
│   │   │   └── BatchAssign.tsx  # supervisor assigns batches
│   │   ├── policies/
│   │   │   ├── RiskModelList.tsx
│   │   │   ├── PolicyEditor.tsx
│   │   │   └── RuleEditor.tsx   # KQL rule editor
│   │   ├── admin/
│   │   │   ├── UserList.tsx
│   │   │   ├── GroupManager.tsx
│   │   │   └── DecisionStatusConfig.tsx
│   │   ├── audit/
│   │   │   └── AuditLog.tsx     # filterable audit trail
│   │   └── dashboard/
│   │       ├── Dashboard.tsx    # overview metrics
│   │       ├── AlertsByChannel.tsx
│   │       ├── AlertsBySeverity.tsx
│   │       └── ReviewProgress.tsx
│   │
│   ├── pages/
│   │   ├── LoginPage.tsx
│   │   ├── DashboardPage.tsx
│   │   ├── AlertsPage.tsx
│   │   ├── AlertDetailPage.tsx
│   │   ├── MessagesPage.tsx
│   │   ├── MessageDetailPage.tsx
│   │   ├── QueuesPage.tsx
│   │   ├── QueueDetailPage.tsx
│   │   ├── PoliciesPage.tsx
│   │   ├── AdminPage.tsx
│   │   └── AuditPage.tsx
│   │
│   └── lib/
│       ├── types.ts             # shared TypeScript types (mirror backend schemas)
│       ├── constants.ts         # severity levels, channels, statuses
│       └── utils.ts             # date formatting, role checks, etc.
│
├── public/
│   └── favicon.svg
└── tests/
    ├── setup.ts
    ├── AlertTable.test.tsx
    └── ...
```

---

## 4. API Design

All endpoints are prefixed with `/api/v1`. Request/response bodies are JSON. Authentication via `Authorization: Bearer <jwt>`.

### 4.1 Authentication

| Method | Path | Role | Description |
|---|---|---|---|
| `POST` | `/auth/login` | public | Authenticate with username + password, returns JWT |
| `POST` | `/auth/refresh` | authenticated | Refresh an expiring token |
| `GET` | `/auth/me` | authenticated | Return current user profile + resolved roles |

JWT payload: `{ sub: user_id, roles: ["reviewer", "supervisor"], exp: ... }`

Role resolution follows the existing chain: `user → user_groups → group_roles → roles`.

### 4.2 Alert Review (core workflow)

| Method | Path | Role | Description |
|---|---|---|---|
| `GET` | `/alerts` | reviewer+ | List alerts with filters (severity, status, channel, date range, rule, policy). **Hybrid query**: PG for alert metadata + ES for message preview |
| `GET` | `/alerts/{id}` | reviewer+ | Alert detail including linked ES document (full message body, participants, enrichments) |
| `PATCH` | `/alerts/{id}/status` | reviewer+ | Update alert status (`open` → `in_review` → `closed`) |
| `GET` | `/alerts/{id}/decisions` | reviewer+ | Decision history for an alert |
| `POST` | `/alerts/{id}/decisions` | reviewer+ | Submit a new decision (status + comment). If `decision_status.is_terminal`, also set `alert.status = closed` |
| `GET` | `/alerts/stats` | supervisor+ | Aggregated counts by severity, status, channel (ES aggregation) |

**Hybrid query pattern for `/alerts`:**
1. Query PG `alert.alerts` with filters (status, severity, date range), paginate
2. Batch-fetch the corresponding ES documents using `es_index` + `es_document_id`
3. Merge PG alert metadata with ES message data into a unified response

### 4.3 Message Search

| Method | Path | Role | Description |
|---|---|---|---|
| `GET` | `/messages/search` | reviewer+ | Full-text search across `messages-*` index. Filters: channel, direction, date range, participant, keyword. Returns paginated results with highlights |
| `GET` | `/messages/{index}/{doc_id}` | reviewer+ | Fetch single ES document by index + document ID |
| `GET` | `/messages/{index}/{doc_id}/audio` | reviewer+ | Generate pre-signed S3 URL for audio playback |

Search parameters map directly to ES queries:
- `q` (body_text, transcript, translated_text) → `multi_match`
- `channel` → `term` filter
- `participants` → `nested` query
- `date_from`, `date_to` → `range` on `timestamp`
- `sentiment` → `term` filter
- `risk_score_min` → `range` filter

### 4.4 Review Queues

| Method | Path | Role | Description |
|---|---|---|---|
| `GET` | `/queues` | supervisor+ | List all review queues |
| `POST` | `/queues` | supervisor+ | Create a queue (name, policy_id) |
| `GET` | `/queues/{id}` | reviewer+ | Queue detail with batches |
| `POST` | `/queues/{id}/batches` | supervisor+ | Create a batch within a queue, optionally auto-populate with matching alerts |
| `PATCH` | `/queues/{id}/batches/{batch_id}` | supervisor+ | Assign batch to reviewer, update status |
| `GET` | `/queues/{id}/batches/{batch_id}/items` | reviewer+ | List queue items (alerts) in a batch, ordered by `position` |
| `GET` | `/my-queue` | reviewer | Get current user's assigned batches across all queues |

### 4.5 Policy & Rule Management

| Method | Path | Role | Description |
|---|---|---|---|
| `GET` | `/risk-models` | reviewer+ | List risk models |
| `POST` | `/risk-models` | admin | Create risk model |
| `PATCH` | `/risk-models/{id}` | admin | Update risk model (name, is_active) |
| `GET` | `/policies` | reviewer+ | List policies (filterable by risk_model_id) |
| `POST` | `/policies` | admin | Create policy under a risk model |
| `PATCH` | `/policies/{id}` | admin | Update policy |
| `GET` | `/policies/{id}/rules` | reviewer+ | List rules for a policy |
| `POST` | `/policies/{id}/rules` | admin | Create rule (name, KQL, severity) |
| `PATCH` | `/rules/{id}` | admin | Update rule |
| `DELETE` | `/rules/{id}` | admin | Deactivate rule (soft delete — `is_active = false`) |

### 4.6 User & Group Administration

| Method | Path | Role | Description |
|---|---|---|---|
| `GET` | `/users` | admin | List users |
| `POST` | `/users` | admin | Create user |
| `PATCH` | `/users/{id}` | admin | Update user (is_active, email) |
| `GET` | `/users/{id}/groups` | admin | User's group memberships |
| `POST` | `/users/{id}/groups` | admin | Add user to group |
| `DELETE` | `/users/{id}/groups/{group_id}` | admin | Remove user from group |
| `GET` | `/groups` | admin | List groups with role/policy counts |
| `POST` | `/groups` | admin | Create group |
| `POST` | `/groups/{id}/roles` | admin | Assign role to group |
| `POST` | `/groups/{id}/policies` | admin | Assign policy to group |

### 4.7 Audit Trail

| Method | Path | Role | Description |
|---|---|---|---|
| `GET` | `/audit-log` | supervisor+ | Read-only log of all decision actions. Filters: actor, alert, date range. Paginated |

### 4.8 Export

| Method | Path | Role | Description |
|---|---|---|---|
| `GET` | `/export/alerts` | supervisor+ | Export alerts as CSV/JSON. Filters match `/alerts` |
| `GET` | `/export/messages` | supervisor+ | Export message search results as CSV/JSON |

---

## 5. Authentication & RBAC

### JWT Flow

```
                          ┌─────────────┐
                          │ POST /login  │
                          │ (username +  │
                          │  password)   │
                          └──────┬───────┘
                                 │
                    ┌────────────▼────────────┐
                    │ Verify password_hash    │
                    │ (bcrypt via passlib)     │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │ Resolve roles:           │
                    │ user → user_groups →     │
                    │ group_roles → roles      │
                    └────────────┬─────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │ Issue JWT                │
                    │ { sub, roles, exp }      │
                    │ (access: 30m, refresh:   │
                    │  7d)                     │
                    └─────────────────────────┘
```

### Role Hierarchy

| Role | Inherits | Can do |
|---|---|---|
| `reviewer` | — | View alerts, search messages, submit decisions on assigned batches |
| `supervisor` | `reviewer` | Create/assign queues, view all batches, export data, view audit log |
| `admin` | `supervisor` | Manage users/groups/roles, configure policies/rules/decision statuses |

Enforcement: FastAPI dependencies that check JWT roles:

```python
# deps.py
def require_role(*roles: str):
    async def check(current_user: User = Depends(get_current_user)):
        if not any(r in current_user.roles for r in roles):
            raise HTTPException(403, "Insufficient permissions")
        return current_user
    return Depends(check)

# Usage in routers:
@router.post("/policies", dependencies=[require_role("admin")])
async def create_policy(...): ...
```

### Phase 2: SSO/OIDC

Replace password-based auth with OpenID Connect (Azure AD, Okta, etc.):
- Add `/.well-known/openid-configuration` discovery
- Exchange OIDC `id_token` for internal JWT
- Map OIDC groups/claims to `iam.groups`
- Keep the internal JWT + RBAC model unchanged

---

## 6. Database Access Pattern

The backend uses **four separate async SQLAlchemy engines**, one per database role, matching the least-privilege model defined in the PostgreSQL schema:

```python
# config.py
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="UMBRELLA_UI_")

    iam_database_url: str          # postgresql+asyncpg://iam_rw:...
    policy_database_url: str       # postgresql+asyncpg://policy_rw:...
    alert_database_url: str        # postgresql+asyncpg://alert_rw:...
    review_database_url: str       # postgresql+asyncpg://review_rw:...
    elasticsearch_url: str         # http://elasticsearch:9200
    jwt_secret: str
    ...
```

```python
# engine.py
iam_engine    = create_async_engine(settings.iam_database_url)
policy_engine = create_async_engine(settings.policy_database_url)
alert_engine  = create_async_engine(settings.alert_database_url)
review_engine = create_async_engine(settings.review_database_url)
```

FastAPI dependencies provide scoped sessions:

```python
async def get_iam_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSession(iam_engine) as session:
        yield session
```

Cross-schema reads (e.g., alert router reading from `alert` + `policy` schemas) use the database role that has read access to both — per the role permissions table:

| DB Role | Read | Write |
|---|---|---|
| `iam_rw` | `iam` | `iam` |
| `policy_rw` | `iam`, `policy` | `policy` |
| `alert_rw` | `iam`, `policy`, `alert` | `alert` |
| `review_rw` | `iam`, `policy`, `alert`, `review` | `review` |

---

## 7. Elasticsearch Query Patterns

### Message Search (`/messages/search`)

```python
async def search_messages(params: MessageSearchParams) -> PaginatedResponse:
    body = {
        "query": {
            "bool": {
                "must": [],
                "filter": []
            }
        },
        "highlight": {
            "fields": {
                "body_text": {},
                "transcript": {},
                "translated_text": {}
            }
        },
        "sort": [{"timestamp": {"order": "desc"}}],
        "from": params.offset,
        "size": params.limit
    }

    if params.q:
        body["query"]["bool"]["must"].append({
            "multi_match": {
                "query": params.q,
                "fields": ["body_text", "transcript", "translated_text"],
                "type": "best_fields"
            }
        })

    if params.channel:
        body["query"]["bool"]["filter"].append({"term": {"channel": params.channel}})

    if params.date_from or params.date_to:
        range_q = {"range": {"timestamp": {}}}
        if params.date_from:
            range_q["range"]["timestamp"]["gte"] = params.date_from.isoformat()
        if params.date_to:
            range_q["range"]["timestamp"]["lte"] = params.date_to.isoformat()
        body["query"]["bool"]["filter"].append(range_q)

    if params.participant:
        body["query"]["bool"]["filter"].append({
            "nested": {
                "path": "participants",
                "query": {
                    "multi_match": {
                        "query": params.participant,
                        "fields": ["participants.name", "participants.id"]
                    }
                }
            }
        })

    result = await es_client.search(index="messages-*", body=body)
    return format_search_response(result)
```

### Alert Dashboard Aggregations (`/alerts/stats`)

```python
async def get_alert_stats() -> AlertStats:
    body = {
        "size": 0,
        "aggs": {
            "by_severity": {"terms": {"field": "severity"}},
            "by_channel": {"terms": {"field": "channel"}},
            "by_status": {"terms": {"field": "review_status"}},
            "over_time": {
                "date_histogram": {
                    "field": "timestamp",
                    "calendar_interval": "day"
                }
            }
        }
    }
    result = await es_client.search(index="alerts-*", body=body)
    return parse_aggregations(result)
```

---

## 8. Frontend Architecture

### Route Map

| Path | Page | Role | Description |
|---|---|---|---|
| `/login` | LoginPage | public | Username + password form |
| `/` | DashboardPage | reviewer+ | Overview: alert counts, severity breakdown, review progress charts |
| `/alerts` | AlertsPage | reviewer+ | Filterable alert table with severity/status/channel columns |
| `/alerts/:id` | AlertDetailPage | reviewer+ | Alert metadata + full ES message + decision history + decision form |
| `/messages` | MessagesPage | reviewer+ | Full-text search interface with filters |
| `/messages/:index/:docId` | MessageDetailPage | reviewer+ | Full message: body, participants, attachments, audio player, enrichments |
| `/queues` | QueuesPage | supervisor+ | Queue list and batch management |
| `/queues/:id` | QueueDetailPage | reviewer+ | Queue batches, items, progress |
| `/policies` | PoliciesPage | admin | Risk models → policies → rules tree view |
| `/admin` | AdminPage | admin | User/group/role management |
| `/audit` | AuditPage | supervisor+ | Audit trail log |

### Key UI Workflows

**1. Alert Review (reviewer's primary workflow)**

```
AlertsPage (table)
  → filter by severity, status, assigned queue
  → click alert row
  → AlertDetailPage
       ├── Alert metadata (severity, rule, policy, created_at)
       ├── Linked message (fetched from ES via es_index + es_document_id)
       │   ├── body_text / transcript
       │   ├── participants
       │   ├── attachments (download links)
       │   ├── audio player (if audio_ref exists)
       │   └── NLP enrichments (entities, sentiment, matched_policies)
       ├── Decision history (past decisions on this alert)
       └── Decision form
            ├── Status dropdown (from review.decision_statuses)
            ├── Comment textarea
            └── Submit button → POST /alerts/{id}/decisions
```

**2. Queue-based Review (supervisor assigns, reviewer works through)**

```
Supervisor:
  QueuesPage → Create Queue (linked to policy)
    → Create Batch → auto-populate with matching alerts or manually add
    → Assign Batch to reviewer

Reviewer:
  /my-queue → see assigned batches
    → BatchView → iterate through queue_items in position order
    → each item links to AlertDetailPage
    → submit decisions sequentially
    → batch status auto-advances to completed when all items decided
```

**3. Message Search (ad-hoc investigation)**

```
MessagesPage
  → enter search query (body_text, transcript)
  → apply filters (channel, date range, participant, sentiment)
  → results show with highlighted matches
  → click result → MessageDetailPage
       ├── full message body
       ├── participant list
       ├── attachments (with S3 download)
       ├── audio player + transcript (if aComm)
       └── linked alerts (if any rules matched this message)
```

---

## 9. Deployment

### Docker Images

**Backend** — `umbrella-ui-backend:latest`

```dockerfile
FROM python:3.13-slim
WORKDIR /app
COPY connectors/connector-framework /app/connector-framework
COPY ui/backend /app/backend
RUN pip install --no-cache-dir /app/connector-framework /app/backend
CMD ["python", "-m", "umbrella_ui"]
```

Build context: repository root (needs `connector-framework` for shared `umbrella_schema` models).

**Frontend** — `umbrella-ui-frontend:latest`

```dockerfile
# Build stage
FROM node:22-alpine AS build
WORKDIR /app
COPY ui/frontend/package.json ui/frontend/package-lock.json ./
RUN npm ci
COPY ui/frontend/ .
RUN npm run build

# Serve stage
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY ui/frontend/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

Nginx config proxies `/api/*` to the backend service.

### Kubernetes Manifests (`deploy/k8s/umbrella-ui/`)

```
deploy/k8s/umbrella-ui/
├── namespace.yaml                # umbrella-ui namespace
├── backend/
│   ├── deployment.yaml           # FastAPI backend (HPA: 2-10 replicas)
│   ├── service.yaml              # ClusterIP on port 8000
│   └── configmap.yaml            # non-secret env vars (ES URL, log level)
├── frontend/
│   ├── deployment.yaml           # nginx serving static assets
│   └── service.yaml              # ClusterIP on port 80
├── secret.yaml                   # DB URLs, JWT secret (or ExternalSecret ref)
└── ingress.yaml                  # Ingress: / → frontend, /api → backend
```

**Backend environment:**

```yaml
env:
  - name: UMBRELLA_UI_IAM_DATABASE_URL
    valueFrom:
      secretKeyRef:
        name: umbrella-ui-credentials
        key: IAM_DATABASE_URL
  - name: UMBRELLA_UI_POLICY_DATABASE_URL
    valueFrom: ...
  - name: UMBRELLA_UI_ALERT_DATABASE_URL
    valueFrom: ...
  - name: UMBRELLA_UI_REVIEW_DATABASE_URL
    valueFrom: ...
  - name: UMBRELLA_UI_ELASTICSEARCH_URL
    value: "http://elasticsearch.umbrella-storage.svc:9200"
  - name: UMBRELLA_UI_JWT_SECRET
    valueFrom:
      secretKeyRef:
        name: umbrella-ui-credentials
        key: JWT_SECRET
  - name: UMBRELLA_UI_S3_ENDPOINT_URL
    value: "http://minio.umbrella-storage.svc:9000"
  - name: UMBRELLA_UI_S3_BUCKET
    value: "umbrella"
```

**Resource sizing (MVP):**

| Component | CPU req/limit | Memory req/limit | Replicas |
|---|---|---|---|
| Backend | 250m / 1000m | 256Mi / 512Mi | 2 (HPA) |
| Frontend | 100m / 250m | 64Mi / 128Mi | 1 |

---

## 10. Implementation Phases

### Phase 1 — Backend Foundation + Auth (Week 1-2)

**Goal:** Runnable backend with authentication and basic CRUD.

1. **Scaffold `ui/backend/` package**
   - `pyproject.toml` with dependencies (fastapi, sqlalchemy[asyncio], asyncpg, elasticsearch[async], python-jose, passlib, structlog, pydantic-settings, boto3)
   - `umbrella_ui/__main__.py` entry point
   - `config.py` with pydantic-settings

2. **Database layer**
   - SQLAlchemy 2.0 async models for all four schemas (mirror the existing migration tables exactly)
   - Four async engines with sessionmaker
   - FastAPI dependencies for scoped sessions

3. **Authentication**
   - `POST /auth/login` — verify bcrypt hash, resolve roles, issue JWT
   - `POST /auth/refresh` — refresh token
   - `GET /auth/me` — return user + roles
   - RBAC dependency (`require_role`)

4. **User & Group admin endpoints**
   - Full CRUD for users, groups, roles
   - Group membership and role assignment

5. **Tests**
   - Auth flow (login, token validation, role checking)
   - User CRUD

**Deliverables:** Backend starts, user can log in, JWT auth works, admin can manage users/groups.

---

### Phase 2 — Alert & Review Workflow (Week 3-4)

**Goal:** Core alert review functionality — the primary business value.

1. **Alert endpoints**
   - `GET /alerts` — PG query with filters + ES batch fetch for message preview
   - `GET /alerts/{id}` — PG alert + ES document
   - `PATCH /alerts/{id}/status`

2. **Decision endpoints**
   - `POST /alerts/{id}/decisions` — create decision, auto-close alert if `is_terminal`
   - `GET /alerts/{id}/decisions` — decision history
   - Audit log auto-population (trigger in PG already exists; backend also writes to `review.audit_log`)

3. **Message search**
   - `GET /messages/search` — ES multi_match with filters and highlighting
   - `GET /messages/{index}/{doc_id}` — single message
   - `GET /messages/{index}/{doc_id}/audio` — S3 pre-signed URL

4. **Queue management**
   - CRUD for queues and batches
   - Batch assignment to reviewers
   - `GET /my-queue` — current user's assigned batches

5. **Tests**
   - Alert listing with filters
   - Decision creation and terminal status handling
   - ES query building
   - Queue assignment flow

**Deliverables:** Full backend API for the alert review workflow.

---

### Phase 3 — Policy Management + Export (Week 5)

**Goal:** Complete the backend API surface.

1. **Policy & rule CRUD**
   - Risk models, policies, rules
   - Group-policy assignment

2. **Audit log endpoint**
   - Read-only, paginated, filterable

3. **Export endpoints**
   - CSV and JSON export for alerts and messages
   - Streaming response for large exports

4. **Alert stats aggregation**
   - ES aggregations for dashboard metrics

5. **Tests**

**Deliverables:** Backend API 100% complete.

---

### Phase 4 — Frontend Foundation + Login (Week 6-7)

**Goal:** React app scaffolded, login working, basic layout.

1. **Scaffold `ui/frontend/`**
   - Vite + React + TypeScript
   - Tailwind CSS v4 + shadcn/ui setup
   - React Router with auth-guarded routes
   - TanStack Query provider
   - Zustand auth store

2. **Login page**
   - Username/password form
   - JWT stored in memory (Zustand) + httpOnly cookie for refresh

3. **App shell**
   - Sidebar navigation (role-aware — hide admin links for reviewers)
   - Header with user menu + logout

4. **Dashboard page**
   - Alert count cards (by severity)
   - Alert-over-time chart (Recharts)
   - Review progress (assigned/completed batches)

**Deliverables:** Frontend builds and deploys, user can log in, dashboard shows real data.

---

### Phase 5 — Alert Review UI (Week 8-9)

**Goal:** Reviewers can review alerts end-to-end.

1. **Alerts page**
   - TanStack Table with sortable columns (severity, status, channel, date, rule)
   - Filter bar (severity, status, channel, date range)
   - Pagination
   - Click row → navigate to detail

2. **Alert detail page**
   - Alert metadata card
   - Linked message display (body, participants, enrichments)
   - Audio player with transcript (for aComm)
   - Decision history timeline
   - Decision submission form (status dropdown + comment)

3. **My Queue page**
   - Assigned batches list
   - Navigate through batch items in order
   - Progress indicator (X of Y reviewed)

**Deliverables:** Primary reviewer workflow fully functional.

---

### Phase 6 — Message Search + Remaining Views (Week 10-11)

**Goal:** Complete all frontend views.

1. **Message search page**
   - Search bar with full-text query
   - Filter sidebar (channel, date, participant, sentiment, risk score)
   - Results with highlighted matches
   - Click → message detail

2. **Message detail page**
   - Full message body
   - Participant list
   - Attachments with download links
   - Audio player (if applicable)
   - NLP enrichments (entities, sentiment score)
   - Linked alerts (if any)

3. **Queue management pages** (supervisor)
   - Create queues, create batches
   - Assign batches to reviewers
   - Monitor batch progress

4. **Policy management pages** (admin)
   - Risk model → policy → rule tree view
   - KQL rule editor with syntax highlighting
   - Toggle active/inactive
   - Group-policy assignment

5. **Admin pages**
   - User list, create/edit user
   - Group management (members + roles)
   - Decision status configuration

6. **Audit log page**
   - Filterable table (actor, alert, date range)
   - JSON detail view for old_values/new_values

**Deliverables:** All frontend views complete.

---

### Phase 7 — Dockerfiles, K8s Manifests, Polish (Week 12)

**Goal:** Production-ready deployment.

1. **Docker images**
   - Backend Dockerfile
   - Frontend Dockerfile (multi-stage with nginx)
   - Add to `scripts/build-images.sh`

2. **K8s manifests**
   - `deploy/k8s/umbrella-ui/` — namespace, deployments, services, configmap, secret, ingress

3. **nginx config**
   - Serve frontend static files
   - Proxy `/api/*` to backend
   - Gzip, cache headers for static assets

4. **Integration testing**
   - End-to-end: login → search → review alert → submit decision → verify audit log
   - Add to minikube test script

5. **Polish**
   - Loading states, error boundaries
   - Responsive layout
   - Keyboard navigation for alert review (next/previous)

**Deliverables:** UI layer deploys to K8s alongside existing infrastructure.

---

## 11. Files to Create

### Backend (ui/backend/)

| File | Purpose |
|---|---|
| `ui/backend/pyproject.toml` | Package metadata + dependencies |
| `ui/backend/Dockerfile` | Docker image |
| `ui/backend/umbrella_ui/__init__.py` | Package init |
| `ui/backend/umbrella_ui/__main__.py` | `uvicorn` entry point |
| `ui/backend/umbrella_ui/app.py` | FastAPI app factory, lifespan, middleware |
| `ui/backend/umbrella_ui/config.py` | Pydantic-settings config |
| `ui/backend/umbrella_ui/deps.py` | FastAPI dependency injection |
| `ui/backend/umbrella_ui/db/engine.py` | Async SQLAlchemy engines |
| `ui/backend/umbrella_ui/db/models/iam.py` | ORM: User, Role, Group, UserGroup, GroupRole |
| `ui/backend/umbrella_ui/db/models/policy.py` | ORM: RiskModel, Policy, Rule, GroupPolicy |
| `ui/backend/umbrella_ui/db/models/alert.py` | ORM: Alert |
| `ui/backend/umbrella_ui/db/models/review.py` | ORM: Queue, Batch, Item, DecisionStatus, Decision, AuditLog |
| `ui/backend/umbrella_ui/es/client.py` | Async ES client wrapper |
| `ui/backend/umbrella_ui/es/queries.py` | ES query builders |
| `ui/backend/umbrella_ui/es/models.py` | Pydantic ES response models |
| `ui/backend/umbrella_ui/auth/jwt.py` | JWT creation/validation |
| `ui/backend/umbrella_ui/auth/password.py` | Bcrypt hashing |
| `ui/backend/umbrella_ui/auth/rbac.py` | Role-checking dependencies |
| `ui/backend/umbrella_ui/auth/schemas.py` | Auth request/response schemas |
| `ui/backend/umbrella_ui/routers/auth.py` | Auth endpoints |
| `ui/backend/umbrella_ui/routers/users.py` | User admin endpoints |
| `ui/backend/umbrella_ui/routers/groups.py` | Group admin endpoints |
| `ui/backend/umbrella_ui/routers/policies.py` | Policy CRUD |
| `ui/backend/umbrella_ui/routers/risk_models.py` | Risk model CRUD |
| `ui/backend/umbrella_ui/routers/alerts.py` | Alert listing + detail |
| `ui/backend/umbrella_ui/routers/messages.py` | Message search + detail |
| `ui/backend/umbrella_ui/routers/queues.py` | Queue/batch management |
| `ui/backend/umbrella_ui/routers/decisions.py` | Decision submission |
| `ui/backend/umbrella_ui/routers/audit.py` | Audit log (read-only) |
| `ui/backend/umbrella_ui/routers/export.py` | CSV/JSON export |
| `ui/backend/umbrella_ui/schemas/common.py` | Shared schemas (pagination, sorting) |
| `ui/backend/umbrella_ui/schemas/iam.py` | User/group request/response schemas |
| `ui/backend/umbrella_ui/schemas/policy.py` | Policy/rule schemas |
| `ui/backend/umbrella_ui/schemas/alert.py` | Alert schemas |
| `ui/backend/umbrella_ui/schemas/review.py` | Queue/decision schemas |
| `ui/backend/umbrella_ui/schemas/message.py` | ES message schemas |
| `ui/backend/umbrella_ui/schemas/export.py` | Export schemas |
| `ui/backend/tests/conftest.py` | Test fixtures |
| `ui/backend/tests/test_auth.py` | Auth tests |
| `ui/backend/tests/test_users.py` | User CRUD tests |
| `ui/backend/tests/test_alerts.py` | Alert tests |
| `ui/backend/tests/test_messages.py` | Message search tests |
| `ui/backend/tests/test_queues.py` | Queue tests |
| `ui/backend/tests/test_decisions.py` | Decision tests |
| `ui/backend/tests/test_policies.py` | Policy tests |

### Frontend (ui/frontend/)

| File | Purpose |
|---|---|
| `ui/frontend/package.json` | Dependencies + scripts |
| `ui/frontend/tsconfig.json` | TypeScript config |
| `ui/frontend/vite.config.ts` | Vite config with API proxy |
| `ui/frontend/Dockerfile` | Multi-stage Docker image |
| `ui/frontend/nginx.conf` | Nginx reverse proxy config |
| `ui/frontend/index.html` | HTML entry point |
| `ui/frontend/src/main.tsx` | React root |
| `ui/frontend/src/App.tsx` | Route definitions |
| `ui/frontend/src/api/client.ts` | HTTP client with JWT interceptor |
| `ui/frontend/src/api/*.ts` | API modules (auth, alerts, messages, etc.) |
| `ui/frontend/src/hooks/*.ts` | TanStack Query hooks |
| `ui/frontend/src/stores/auth.ts` | Zustand auth store |
| `ui/frontend/src/components/**/*.tsx` | UI components (see section 3) |
| `ui/frontend/src/pages/*.tsx` | Page components (see section 3) |
| `ui/frontend/src/lib/types.ts` | Shared TypeScript types |
| `ui/frontend/src/lib/constants.ts` | Enums + constants |
| `ui/frontend/src/lib/utils.ts` | Utility functions |

### Kubernetes

| File | Purpose |
|---|---|
| `deploy/k8s/umbrella-ui/namespace.yaml` | Namespace |
| `deploy/k8s/umbrella-ui/backend/deployment.yaml` | Backend Deployment + HPA |
| `deploy/k8s/umbrella-ui/backend/service.yaml` | Backend ClusterIP |
| `deploy/k8s/umbrella-ui/backend/configmap.yaml` | Backend non-secret config |
| `deploy/k8s/umbrella-ui/frontend/deployment.yaml` | Frontend (nginx) Deployment |
| `deploy/k8s/umbrella-ui/frontend/service.yaml` | Frontend ClusterIP |
| `deploy/k8s/umbrella-ui/secret.yaml` | DB URLs, JWT secret |
| `deploy/k8s/umbrella-ui/ingress.yaml` | Ingress routing |

---

## 12. Dependencies on Existing Infrastructure

| Dependency | Location | Status |
|---|---|---|
| PostgreSQL (4 schemas, 6 migrations) | `infrastructure/postgresql/migrations/` | Implemented |
| PostgreSQL K8s manifests | `deploy/k8s/umbrella-storage/postgresql/` | Implemented |
| Elasticsearch (messages-*, alerts-* indices) | `infrastructure/elasticsearch/` | Implemented |
| Elasticsearch K8s manifests | `deploy/k8s/umbrella-storage/elasticsearch/` | Implemented |
| S3/MinIO (attachments, audio) | `deploy/k8s/umbrella-storage/minio/` | Implemented |
| `umbrella_schema` (NormalizedMessage) | `connectors/connector-framework/` | Implemented |
| Kafka (normalized-messages, alerts topics) | `deploy/k8s/umbrella-streaming/` | Implemented |
| Logstash (Kafka → ES indexing) | `deploy/k8s/umbrella-storage/logstash/` | Implemented |

All upstream dependencies are already built. The UI layer is the final component in the platform.

---

## 13. Open Questions / Decisions for Later

1. **WebSocket for real-time alerts** — push new alerts to the dashboard via WebSocket instead of polling? (Phase 2+)
2. **Case management integration** — define the API contract for escalating alerts to an external case manager (webhook or REST callback)
3. **SSO/OIDC provider** — which identity provider (Azure AD, Okta, Keycloak)? Defer to Phase 2
4. **Multi-tenancy** — is the platform single-tenant or does it need org-level isolation?
5. **Attachment preview** — render PDF/image attachments inline or download-only?
6. **KQL validation** — should the rule editor validate KQL syntax client-side before saving?
