# Phase 3 — Policy Management + Export (Detailed Plan)

**Goal:** Complete the backend API surface. After this phase, every endpoint in the API design (sections 4.1–4.8 of `ui-layer-plan.md`) is implemented and tested.

**Prerequisites:** Phase 1 (auth, users, groups) and Phase 2 (alerts, decisions, messages, queues, audit) are complete.

---

## What Already Exists

These items were built in Phase 1–2 and do **not** need to be recreated:

| Item | File | Status |
|---|---|---|
| SQLAlchemy models (RiskModel, Policy, Rule, GroupPolicy) | `db/models/policy.py` | Complete |
| Audit log endpoint (`GET /audit-log`) | `routers/audit.py` | Complete |
| Alert stats endpoint (`GET /alerts/stats`) | `routers/alerts.py` | Complete |
| ES query builder (`build_alert_stats`) | `es/queries.py` | Complete |
| `get_policy_session` dependency | `deps.py` | Complete |

## What Phase 3 Creates

| # | Deliverable | New file(s) |
|---|---|---|
| 1 | Policy schemas | `schemas/policy.py` |
| 2 | Risk model CRUD endpoints | `routers/risk_models.py` |
| 3 | Policy + rule CRUD endpoints | `routers/policies.py` |
| 4 | Group-policy assignment endpoints | `routers/policies.py` (or `groups.py` extension) |
| 5 | Export schemas | `schemas/export.py` |
| 6 | Export endpoints (CSV + JSON) | `routers/export.py` |
| 7 | Enhanced alert stats (optional filters) | `routers/alerts.py` + `es/queries.py` (modify) |
| 8 | `override_policy_session` test helper | `tests/conftest.py` (modify) |
| 9 | Tests | `tests/test_risk_models.py`, `tests/test_policies.py`, `tests/test_export.py` |
| 10 | Router registration | `app.py` (modify) |

---

## 1. Pydantic Schemas — `schemas/policy.py`

Follows the pattern in `schemas/iam.py` and `schemas/review.py`: separate Create/Update/Out models.

```python
# --- Risk models ---

class RiskModelCreate(BaseModel):
    name: str
    description: str | None = None

class RiskModelUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None

class RiskModelOut(BaseModel):
    id: UUID
    name: str
    description: str | None
    is_active: bool
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime

class RiskModelDetail(RiskModelOut):
    policy_count: int            # count of child policies


# --- Policies ---

class PolicyCreate(BaseModel):
    name: str
    description: str | None = None

class PolicyUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None

class PolicyOut(BaseModel):
    id: UUID
    risk_model_id: UUID
    name: str
    description: str | None
    is_active: bool
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime

class PolicyDetail(PolicyOut):
    risk_model_name: str         # denormalized for convenience
    rule_count: int              # count of child rules
    group_count: int             # count of assigned groups


# --- Rules ---

class RuleCreate(BaseModel):
    name: str
    description: str | None = None
    kql: str                     # KQL expression
    severity: str                # low | medium | high | critical

class RuleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    kql: str | None = None
    severity: str | None = None
    is_active: bool | None = None

class RuleOut(BaseModel):
    id: UUID
    policy_id: UUID
    name: str
    description: str | None
    kql: str
    severity: str
    is_active: bool
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime


# --- Group-policy assignment ---

class AssignGroupPolicy(BaseModel):
    group_id: UUID

class GroupPolicyOut(BaseModel):
    group_id: UUID
    policy_id: UUID
    assigned_by: UUID | None
    assigned_at: datetime
```

### Validation Notes

- `RuleCreate.severity` should be validated with a `Literal["low", "medium", "high", "critical"]` or a `field_validator` to match the DB CHECK constraint.
- `RuleUpdate.severity` same treatment (optional, but validated when present).

---

## 2. Risk Model CRUD — `routers/risk_models.py`

**Prefix:** `/api/v1/risk-models` · **Tag:** `risk-models`

**DB session:** `get_policy_session` (role `policy_rw` has read/write on `policy` schema, read on `iam`).

| Endpoint | Method | Role | Description |
|---|---|---|---|
| `/risk-models` | `GET` | reviewer+ | List risk models, paginated. Returns `PaginatedResponse[RiskModelDetail]` with `policy_count` per model |
| `/risk-models` | `POST` | admin | Create risk model. Sets `created_by` from JWT `sub`. Returns `RiskModelOut` (201) |
| `/risk-models/{id}` | `GET` | reviewer+ | Single risk model detail (with `policy_count`) |
| `/risk-models/{id}` | `PATCH` | admin | Update name, description, or `is_active`. Returns `RiskModelOut` |

### Implementation Details

**List:**
```python
@router.get("", response_model=PaginatedResponse[RiskModelDetail])
async def list_risk_models(
    session: Annotated[AsyncSession, Depends(get_policy_session)],
    _user: Annotated[dict, Depends(require_role("reviewer"))],
    is_active: bool | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
):
```
- Base query: `select(RiskModel)`
- Optional filter: `.where(RiskModel.is_active == is_active)` when param is not None
- Count child policies per model (subquery or post-fetch loop — follow the `_group_detail` pattern from `groups.py`)
- Order by `name` ascending

**Create:**
- `IntegrityError` → 409 "Risk model name already exists" (name is UNIQUE)
- Set `created_by = current_user["id"]`

**Update:**
- Fetch by ID, 404 if not found
- Apply non-None fields from `RiskModelUpdate`
- `IntegrityError` on name change → 409

---

## 3. Policy + Rule CRUD — `routers/policies.py`

**Prefix:** `/api/v1/policies` · **Tag:** `policies`

**DB session:** `get_policy_session`

### 3a. Policy Endpoints

| Endpoint | Method | Role | Description |
|---|---|---|---|
| `/policies` | `GET` | reviewer+ | List policies, filterable by `risk_model_id` and `is_active`. Returns `PaginatedResponse[PolicyDetail]` |
| `/policies` | `POST` | admin | Create policy under a risk model (`risk_model_id` in request body). Returns `PolicyOut` (201) |
| `/policies/{id}` | `GET` | reviewer+ | Policy detail with `rule_count`, `group_count`, `risk_model_name` |
| `/policies/{id}` | `PATCH` | admin | Update name, description, `is_active`. Returns `PolicyOut` |

**PolicyCreate note:** The `risk_model_id` goes in the request body (not the URL), since it's a required FK:

```python
class PolicyCreate(BaseModel):
    risk_model_id: UUID      # moved here from the URL-based plan
    name: str
    description: str | None = None
```

Alternatively, use nested URL (`POST /risk-models/{rm_id}/policies`), but the flat design from `ui-layer-plan.md` section 4.5 uses a top-level `/policies` with `risk_model_id` as a body field. Stick with the plan.

**List details:**
- Join `RiskModel` to get `risk_model_name`
- Count rules: subquery `select(func.count()).select_from(Rule).where(Rule.policy_id == Policy.id)`
- Count groups: subquery `select(func.count()).select_from(GroupPolicy).where(GroupPolicy.policy_id == Policy.id)`
- Follow the `_group_detail` helper pattern from `groups.py`

**Create:**
- Verify `risk_model_id` exists (fetch RiskModel, 404 if not found)
- `IntegrityError` → 409 "Policy name already exists for this risk model" (unique: `(risk_model_id, name)`)
- Set `created_by = current_user["id"]`

### 3b. Rule Endpoints

| Endpoint | Method | Role | Description |
|---|---|---|---|
| `/policies/{policy_id}/rules` | `GET` | reviewer+ | List rules for a policy. Returns `PaginatedResponse[RuleOut]` |
| `/policies/{policy_id}/rules` | `POST` | admin | Create rule under a policy. Returns `RuleOut` (201) |
| `/rules/{id}` | `GET` | reviewer+ | Single rule detail |
| `/rules/{id}` | `PATCH` | admin | Update rule fields. Returns `RuleOut` |
| `/rules/{id}` | `DELETE` | admin | Soft-delete: set `is_active = false`. Returns 204 |

**Create rule:**
- Verify `policy_id` exists (fetch Policy, 404 if not found)
- Validate `severity` is one of `low`, `medium`, `high`, `critical` (Pydantic `Literal` or manual check)
- Set `created_by = current_user["id"]`

**Delete rule (soft):**
- Fetch by ID, 404 if not found
- Set `is_active = False`, commit
- Return 204 No Content

**Note on `DELETE /rules/{id}` route:** This uses a top-level `/rules/{id}` path (not nested under `/policies`). To keep this in the same router file, define a second `APIRouter` or use a single router with both prefixes. Simplest approach: define the `/rules/{id}` endpoints in the same `policies.py` file using a separate `rules_router = APIRouter(prefix="/api/v1/rules", tags=["rules"])`, and include both routers in `app.py`.

### 3c. Group-Policy Assignment

| Endpoint | Method | Role | Description |
|---|---|---|---|
| `/policies/{policy_id}/groups` | `GET` | admin | List groups assigned to a policy. Returns `list[GroupPolicyOut]` |
| `/policies/{policy_id}/groups` | `POST` | admin | Assign a group to a policy. Body: `{ group_id: UUID }`. Returns 200 |
| `/policies/{policy_id}/groups/{group_id}` | `DELETE` | admin | Remove group-policy assignment. Returns 204 |

**Implementation:**
- These endpoints use `get_policy_session` since `GroupPolicy` is in the `policy` schema
- On POST: verify both `policy_id` and `group_id` exist (group check reads from `iam.groups` — `policy_rw` has read access to `iam`)
- `IntegrityError` → 409 "Group already assigned to this policy"
- On DELETE: `delete(GroupPolicy).where(group_id=..., policy_id=...)`

These live in `routers/policies.py` alongside the other policy endpoints.

---

## 4. Export Endpoints — `routers/export.py`

**Prefix:** `/api/v1/export` · **Tag:** `export`

| Endpoint | Method | Role | Description |
|---|---|---|---|
| `/export/alerts` | `GET` | supervisor+ | Export alerts as CSV or JSON |
| `/export/messages` | `GET` | supervisor+ | Export message search results as CSV or JSON |

### 4a. Schemas — `schemas/export.py`

```python
from enum import Enum

class ExportFormat(str, Enum):
    csv = "csv"
    json = "json"
```

No complex response schema needed — CSV returns `text/csv`, JSON returns `application/json` (array of objects).

### 4b. Alert Export — `GET /export/alerts`

**Query parameters:** Same filters as `GET /alerts` (severity, status, rule_id) plus:
- `format`: `csv` | `json` (default: `csv`)

**Implementation:**
1. Query PG `alert.alerts` with the same filter logic as `routers/alerts.py:list_alerts`
2. Remove pagination (no `offset`/`limit`) — but enforce a **max row cap** (e.g., 10,000) to prevent memory issues
3. For CSV: use `StreamingResponse` with `text/csv` content type
4. For JSON: use `StreamingResponse` with `application/json` content type

**CSV streaming pattern:**
```python
import csv
import io
from fastapi.responses import StreamingResponse

async def _stream_alerts_csv(alerts):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["id", "name", "severity", "status", "rule_id", "es_index", "es_document_id", "created_at"])
    yield buffer.getvalue()
    buffer.seek(0)
    buffer.truncate(0)

    for alert in alerts:
        writer.writerow([
            str(alert.id), alert.name, alert.severity, alert.status,
            str(alert.rule_id), alert.es_index, alert.es_document_id,
            alert.created_at.isoformat(),
        ])
        yield buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)
```

Return with `Content-Disposition: attachment; filename="alerts-export-{timestamp}.csv"` header.

**JSON export:**
- Serialize each alert as a dict, collect into a list, return as a JSON array
- Use `StreamingResponse` with line-delimited chunks for large exports

### 4c. Message Export — `GET /export/messages`

**Query parameters:** Same as `GET /messages/search` (q, channel, direction, participant, date_from, date_to, sentiment, risk_score_min) plus:
- `format`: `csv` | `json`

**Implementation:**
1. Build ES query using the existing `build_message_search()` from `es/queries.py`
2. Use ES **scroll API** (or `search_after`) for large result sets instead of from/size pagination
3. Stream results as CSV or JSON

**ES scroll pattern:**
```python
async def _scroll_messages(es, query_body, max_results=10000):
    """Yield ES message hits using the scroll API."""
    query_body.pop("from", None)
    query_body["size"] = 1000  # per-scroll batch

    resp = await es.search(index="messages-*", body=query_body, scroll="2m")
    scroll_id = resp["_scroll_id"]
    hits = resp["hits"]["hits"]
    count = 0

    try:
        while hits and count < max_results:
            for hit in hits:
                yield hit["_source"]
                count += 1
                if count >= max_results:
                    break
            resp = await es.scroll(scroll_id=scroll_id, scroll="2m")
            scroll_id = resp["_scroll_id"]
            hits = resp["hits"]["hits"]
    finally:
        await es.clear_scroll(scroll_id=scroll_id)
```

**CSV columns for messages:** `message_id`, `channel`, `direction`, `timestamp`, `participants` (semicolon-separated names), `body_text` (truncated to 500 chars), `sentiment`, `risk_score`

---

## 5. Enhanced Alert Stats (Optional Filters)

Extend the existing `GET /alerts/stats` endpoint and `build_alert_stats()` query builder to accept optional filters.

### Changes to `es/queries.py`

```python
def build_alert_stats(
    *,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    policy_id: str | None = None,
    severity: str | None = None,
) -> dict:
```

Add a `"query"` key with a `bool/filter` array when filters are present. When no filters, keep the existing `{"match_all": {}}` behavior.

### Changes to `routers/alerts.py`

Add optional query params to the existing `get_alert_stats` endpoint:

```python
@router.get("/stats", response_model=AlertStats)
async def get_alert_stats(
    es: Annotated[AsyncElasticsearch, Depends(get_es)],
    _user: Annotated[dict, Depends(require_role("supervisor"))],
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    severity: str | None = Query(default=None),
):
```

This is a backward-compatible change — existing calls without filters still work identically.

---

## 6. Test Fixtures — `tests/conftest.py` Additions

Add a `override_policy_session` helper (follows existing `override_alert_session` pattern):

```python
from umbrella_ui.deps import get_policy_session

def override_policy_session(app, session):
    async def _get_session():
        yield session
    app.dependency_overrides[get_policy_session] = _get_session
```

---

## 7. Tests

### 7a. `tests/test_risk_models.py`

| Test | Description |
|---|---|
| `test_list_risk_models` | GET returns paginated list with `policy_count`, reviewer can access |
| `test_list_risk_models_filter_active` | GET with `?is_active=true` filters correctly |
| `test_create_risk_model` | POST creates, returns 201, admin only |
| `test_create_risk_model_duplicate` | POST with duplicate name returns 409 |
| `test_create_risk_model_reviewer_forbidden` | POST by reviewer returns 403 |
| `test_get_risk_model` | GET by ID returns detail |
| `test_get_risk_model_not_found` | GET unknown ID returns 404 |
| `test_update_risk_model` | PATCH updates fields, admin only |
| `test_update_risk_model_deactivate` | PATCH `is_active=false` |

### 7b. `tests/test_policies.py`

| Test | Description |
|---|---|
| `test_list_policies` | GET returns paginated list with `rule_count`, `group_count` |
| `test_list_policies_filter_by_risk_model` | GET with `?risk_model_id=...` |
| `test_create_policy` | POST creates under risk model, returns 201 |
| `test_create_policy_risk_model_not_found` | POST with bad `risk_model_id` returns 404 |
| `test_create_policy_duplicate_name` | POST duplicate name under same risk model returns 409 |
| `test_get_policy_detail` | GET by ID includes `risk_model_name`, `rule_count`, `group_count` |
| `test_update_policy` | PATCH updates fields |
| `test_list_rules` | GET `/policies/{id}/rules` returns rules |
| `test_create_rule` | POST creates rule under policy, returns 201 |
| `test_create_rule_invalid_severity` | POST with bad severity returns 422 |
| `test_create_rule_policy_not_found` | POST under non-existent policy returns 404 |
| `test_get_rule` | GET `/rules/{id}` returns rule |
| `test_update_rule` | PATCH updates rule fields |
| `test_delete_rule_soft` | DELETE sets `is_active=false`, returns 204 |
| `test_list_group_policies` | GET `/policies/{id}/groups` |
| `test_assign_group_policy` | POST assigns group to policy |
| `test_assign_group_policy_duplicate` | POST duplicate returns 409 |
| `test_remove_group_policy` | DELETE returns 204 |

### 7c. `tests/test_export.py`

| Test | Description |
|---|---|
| `test_export_alerts_csv` | GET returns `text/csv` with header row + data rows |
| `test_export_alerts_json` | GET with `?format=json` returns JSON array |
| `test_export_alerts_with_filters` | Filters (severity, status) are applied |
| `test_export_alerts_supervisor_only` | Reviewer gets 403 |
| `test_export_messages_csv` | GET returns CSV from ES results |
| `test_export_messages_json` | GET with `?format=json` returns JSON array |
| `test_export_messages_empty` | Empty result set returns header-only CSV |

### Testing Pattern (matches existing tests)

All tests use the established mock pattern:
1. `make_session_mock()` or custom `AsyncMock` for DB sessions
2. `AsyncMock()` for ES client
3. `override_policy_session(app, session)` for policy router tests
4. `make_admin_headers(settings)` for admin-only endpoints
5. `make_reviewer_headers(settings)` for reviewer-accessible endpoints
6. `make_supervisor_headers(settings)` for supervisor-only exports

---

## 8. Router Registration — `app.py`

Add three new router imports and `include_router` calls:

```python
from umbrella_ui.routers.policies import router as policies_router
from umbrella_ui.routers.policies import rules_router  # separate prefix for /rules/{id}
from umbrella_ui.routers.risk_models import router as risk_models_router
from umbrella_ui.routers.export import router as export_router

app.include_router(risk_models_router)
app.include_router(policies_router)
app.include_router(rules_router)
app.include_router(export_router)
```

---

## 9. Implementation Order

Build sequentially — each step depends on the previous:

### Step 1: Schemas (`schemas/policy.py`, `schemas/export.py`)
- Create all Pydantic models listed in section 1 and 4a
- No external dependencies, pure data classes

### Step 2: Risk Model Router (`routers/risk_models.py`)
- 4 endpoints: list, create, get, update
- Register in `app.py`
- Follows `groups.py` CRUD pattern exactly

### Step 3: Policy + Rule Router (`routers/policies.py`)
- Policy CRUD (4 endpoints)
- Rule CRUD (5 endpoints, including `/rules/{id}` routes)
- Group-policy assignment (3 endpoints)
- Register both routers in `app.py`

### Step 4: Export Router (`routers/export.py`)
- Alert export (CSV/JSON)
- Message export (CSV/JSON with ES scroll)
- Register in `app.py`

### Step 5: Enhanced Alert Stats
- Modify `es/queries.py:build_alert_stats()` to accept filters
- Modify `routers/alerts.py:get_alert_stats` to pass filter params
- Backward-compatible — existing behavior unchanged

### Step 6: Test Fixtures
- Add `override_policy_session` to `tests/conftest.py`

### Step 7: Tests
- `test_risk_models.py` (9 tests)
- `test_policies.py` (17 tests)
- `test_export.py` (7 tests)
- Run full suite: `pytest ui/backend/tests/ -v`

---

## 10. Files Changed / Created Summary

| Action | File |
|---|---|
| **Create** | `ui/backend/umbrella_ui/schemas/policy.py` |
| **Create** | `ui/backend/umbrella_ui/schemas/export.py` |
| **Create** | `ui/backend/umbrella_ui/routers/risk_models.py` |
| **Create** | `ui/backend/umbrella_ui/routers/policies.py` |
| **Create** | `ui/backend/umbrella_ui/routers/export.py` |
| **Create** | `ui/backend/tests/test_risk_models.py` |
| **Create** | `ui/backend/tests/test_policies.py` |
| **Create** | `ui/backend/tests/test_export.py` |
| **Modify** | `ui/backend/umbrella_ui/app.py` — register 3 new routers |
| **Modify** | `ui/backend/umbrella_ui/es/queries.py` — add filter params to `build_alert_stats()` |
| **Modify** | `ui/backend/umbrella_ui/routers/alerts.py` — pass filter params to stats query |
| **Modify** | `ui/backend/tests/conftest.py` — add `override_policy_session` helper |

**No new DB migrations required** — all tables already exist from V1–V6 migrations.

**No new dependencies required** — `csv`, `io` are stdlib; all other deps (fastapi, sqlalchemy, elasticsearch, boto3) are already installed.

---

## 11. Endpoint Count

| Area | Endpoints | New / Existing |
|---|---|---|
| Risk models | 4 | New |
| Policies | 4 | New |
| Rules | 5 | New |
| Group-policy | 3 | New |
| Export | 2 | New |
| Alert stats (enhanced) | 1 | Modified |
| Audit log | 1 | Already complete |
| **Total** | **20** | **18 new + 1 modified + 1 existing** |

After Phase 3, the full backend API surface is: **auth (3) + users (7) + groups (6) + roles (1) + alerts (4) + decisions (3) + messages (3) + queues (7) + audit (1) + risk models (4) + policies (4) + rules (5) + group-policy (3) + export (2) = 53 endpoints**.
