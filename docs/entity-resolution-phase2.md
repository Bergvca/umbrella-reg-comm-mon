# Entity Resolution Phase 2 — End-to-End Integration Plan

## Context

Phase 1 built entity CRUD (Postgres tables, backend API, frontend pages) and inline resolution during ingestion. However, entity data stops at Kafka/S3 — it never reaches Elasticsearch. This means the UI can't show entity links on messages/alerts, agents can't query by entity attributes, and alerts aren't linked to entities. This plan closes those gaps.

---

## 1. Flow entity_id/entity_name into Elasticsearch

### 1a. Update ES index template

**File:** `infrastructure/elasticsearch/config/index-templates/messages-template.json`

Add `entity_id` (keyword) and `entity_name` (keyword) to the `participants` nested mapping:
```json
"participants": {
  "type": "nested",
  "properties": {
    "id": { "type": "keyword" },
    "name": { ... },
    "role": { "type": "keyword" },
    "entity_id": { "type": "keyword" },
    "entity_name": { "type": "keyword" }
  }
}
```

Also update the percolator mapping (`infrastructure/elasticsearch/umbrella-alert-rules-mapping.json`) to match — percolator needs identical field definitions for the document being percolated.

### 1b. Include entity fields in the percolation doc

**File:** `ingestion-api/umbrella_ingestion/service.py` — `_dual_write()` line 214-217

Currently strips entity fields:
```python
"participants": [
    {"id": p.id, "name": p.name, "role": p.role}
    for p in normalized.participants
],
```

Change to include entity_id/entity_name:
```python
"participants": [
    {
        "id": p.id, "name": p.name, "role": p.role,
        **({"entity_id": p.entity_id} if p.entity_id else {}),
        **({"entity_name": p.entity_name} if p.entity_name else {}),
    }
    for p in normalized.participants
],
```

Logstash already passes through all JSON fields from Kafka → ES (no field filtering), so the `entity_id`/`entity_name` on the Kafka message will flow through automatically. No Logstash changes needed.

### 1c. Verify with test data

The `scripts/test-pipeline-minikube.sh` script seeds entity "Alice (Test Sender)" with handle `alice@example.com`. After this change, the test event should have `entity_id` populated on the sender participant in ES.

---

## 2. Clickable entities on Message/Alert pages

### 2a. Backend: add entity fields to ESParticipant

**File:** `ui/backend/umbrella_ui/es/models.py`

```python
class ESParticipant(BaseModel):
    id: str
    name: str
    role: str
    entity_id: str | None = None
    entity_name: str | None = None
```

No router changes needed — `get_message()` already returns `ESMessage` which includes `participants`.

### 2b. Frontend: make participants clickable

**File:** `ui/frontend/src/components/messages/ParticipantList.tsx`

In `ParticipantChip`, if `participant.entity_id` is set, wrap the name/id in a `<Link to={/entities/${p.entity_id}}>` so it navigates to the entity detail page.

This component is already used by `MessageDisplay` (and can be reused by alert views). Show a subtle visual indicator (e.g. underline or small icon) when entity is linked.

### 2c. Frontend types already support this

`ui/frontend/src/lib/types.ts` — `Participant` already has optional `entity_id` and `entity_name` fields. No change needed.

---

## 3. Entity detail page: show linked messages and alerts

### 3a. Backend: add entity-linked-messages endpoint

**File:** `ui/backend/umbrella_ui/routers/entities.py`

Add `GET /api/v1/entities/{entity_id}/messages` — uses a nested query on ES:
```json
{
  "query": {
    "nested": {
      "path": "participants",
      "query": { "term": { "participants.entity_id": "<entity_id>" } }
    }
  },
  "sort": [{ "timestamp": "desc" }]
}
```

Returns paginated `ESMessageHit[]`.

### 3b. Backend: add entity-linked-alerts endpoint

**File:** `ui/backend/umbrella_ui/routers/entities.py`

Add `GET /api/v1/entities/{entity_id}/alerts` — query PG directly via the `alert.alert_entities` join table:
```sql
SELECT a.*, r.name AS rule_name, p.name AS policy_name
FROM alert.alerts a
JOIN alert.alert_entities ae ON ae.alert_id = a.id
JOIN policy.rules r ON r.id = a.rule_id
JOIN policy.policies p ON p.id = r.policy_id
WHERE ae.entity_id = :entity_id
ORDER BY a.created_at DESC
```

Returns `AlertOut[]`.

### 3c. Frontend: add Messages and Alerts tabs to EntityDetailPage

**File:** `ui/frontend/src/pages/EntityDetailPage.tsx`

Add two new cards/sections below existing Handles and Attributes:
- **Messages** — table of messages involving this entity, linking to `/messages/{index}/{docId}`
- **Alerts** — table of alerts linked to this entity, linking to alert detail

New hooks in `ui/frontend/src/hooks/useEntities.ts`:
- `useEntityMessages(entityId)` → `GET /api/v1/entities/{id}/messages`
- `useEntityAlerts(entityId)` → `GET /api/v1/entities/{id}/alerts`

New API functions in `ui/frontend/src/api/entities.ts`.

### 3d. Searchable attributes on EntitiesPage

The entity list page already supports search by name and filter by type. Add attribute-based filtering:

**Backend:** extend `GET /api/v1/entities` to accept `attr_key` and `attr_value` query params, adding a JOIN to `entity.attributes` with appropriate WHERE clauses.

**Frontend:** add attribute key/value filter inputs to `EntitiesPage.tsx`.

---

## 4. Link alerts to entities

### 4a. Database: add entity linkage to alert.alerts

**New migration:** `infrastructure/postgresql/migrations/V13__alert_entity_link.sql`

Join table (supports many-to-many — one alert's message can have multiple participant entities):
```sql
CREATE TABLE alert.alert_entities (
    alert_id  UUID NOT NULL REFERENCES alert.alerts(id) ON DELETE CASCADE,
    entity_id UUID NOT NULL REFERENCES entity.entities(id) ON DELETE CASCADE,
    PRIMARY KEY (alert_id, entity_id)
);
CREATE INDEX idx_alert_entities_entity ON alert.alert_entities(entity_id);
```

Also add to the K8s migration ConfigMap in `deploy/k8s/umbrella-storage/postgresql/migration-job.yaml`.

### 4b. Populate alert_entities at percolation time

**File:** `ingestion-api/umbrella_ingestion/percolator.py`

After inserting an alert row, also insert into `alert.alert_entities` for each resolved participant entity_id on the message. The percolator already has the normalized message with entity_ids.

Change `AlertPercolator.percolate()` signature to accept `entity_ids: list[str]` (extracted from the normalized message's participants in `_dual_write`).

### 4c. Backend: expose entity links on alerts

**File:** `ui/backend/umbrella_ui/routers/alerts.py`

When fetching alerts, JOIN to `alert.alert_entities` → `entity.entities` to include linked entity names/IDs in the response. Add to `AlertOut` schema:
```python
linked_entities: list[LinkedEntity] = []

class LinkedEntity(BaseModel):
    entity_id: str
    display_name: str
```

### 4d. Frontend: show entity chips on alert views

In `AlertSidePanel.tsx`, render linked entities as clickable chips/links navigating to `/entities/{id}`.

---

## 5. Agent entity lookup tool

### 5a. New tool: entity_lookup

**File:** `agents/umbrella_agents/tools/entity_lookup.py`

A dedicated LangChain tool that queries entities and their relationships:

```python
class EntityLookupInput(BaseModel):
    entity_name: str | None      # ilike search on display_name
    entity_type: str | None      # filter by type
    handle_value: str | None     # exact match on handle
    attr_key: str | None         # filter by attribute key
    attr_value: str | None       # filter by attribute value (ilike)
    include_alerts: bool = False # join to alert_entities for alert counts
    limit: int = 20
```

Queries PG `entity.*` tables. When `include_alerts=True`, adds a LEFT JOIN to `alert.alert_entities` with count. Returns entity details with handles, attributes, and optionally alert counts.

Example agent query: "Find all alerts for entities in the Trading department" →
1. `entity_lookup(attr_key="department", attr_value="Trading", include_alerts=True)`
2. For entities with alerts, follow up with `alert_lookup` filtered by entity

### 5b. Seed the tool in PG

**New migration:** `infrastructure/postgresql/migrations/V14__seed_entity_lookup_tool.sql`

Insert into `agent.tools`:
```sql
INSERT INTO agent.tools (name, description, tool_type, config)
VALUES ('entity_lookup', 'Look up entities by name, handle, type, or attributes. Can include alert counts.', 'entity_lookup', '{}');
```

### 5c. Register in tool registry

**File:** `agents/umbrella_agents/tools/registry.py` — import and register

### 5d. Enhance alert_lookup with entity filtering

**File:** `agents/umbrella_agents/tools/alert_lookup.py`

Add `entity_name` and `entity_attribute` inputs to `AlertLookupInput`:
```python
entity_name: str | None = Field(default=None, description="Filter alerts linked to entities matching this name")
entity_department: str | None = Field(default=None, description="Filter alerts by entity department attribute")
```

When provided, JOIN through `alert.alert_entities` → `entity.entities` and optionally `entity.attributes` to filter.

---

## Files to modify/create

| File | Action |
|------|--------|
| `infrastructure/elasticsearch/config/index-templates/messages-template.json` | Add entity_id, entity_name to participants |
| `infrastructure/elasticsearch/umbrella-alert-rules-mapping.json` | Add entity_id, entity_name to participants |
| `ingestion-api/umbrella_ingestion/service.py` | Include entity fields in percolation doc |
| `ingestion-api/umbrella_ingestion/percolator.py` | Pass entity_ids when creating alerts, insert alert_entities |
| `ui/backend/umbrella_ui/es/models.py` | Add entity_id, entity_name to ESParticipant |
| `ui/frontend/src/components/messages/ParticipantList.tsx` | Make entity-linked participants clickable |
| `ui/backend/umbrella_ui/routers/entities.py` | Add /messages and /alerts endpoints, attribute filtering |
| `ui/frontend/src/pages/EntityDetailPage.tsx` | Add Messages and Alerts sections |
| `ui/frontend/src/hooks/useEntities.ts` | Add useEntityMessages, useEntityAlerts hooks |
| `ui/frontend/src/api/entities.ts` | Add getEntityMessages, getEntityAlerts API functions |
| `ui/frontend/src/pages/EntitiesPage.tsx` | Add attribute filtering |
| `infrastructure/postgresql/migrations/V13__alert_entity_link.sql` | Create alert.alert_entities table |
| `deploy/k8s/umbrella-storage/postgresql/migration-job.yaml` | Add V13 SQL to ConfigMap |
| `ui/backend/umbrella_ui/routers/alerts.py` | Include linked entities in alert responses |
| `ui/backend/umbrella_ui/schemas/alert.py` | Add LinkedEntity to AlertOut |
| `ui/frontend/src/components/alerts/AlertSidePanel.tsx` | Show linked entity chips |
| `agents/umbrella_agents/tools/entity_lookup.py` | **New** — entity lookup tool |
| `infrastructure/postgresql/migrations/V14__seed_entity_lookup_tool.sql` | **New** — seed tool |
| `agents/umbrella_agents/tools/alert_lookup.py` | Add entity-based filtering |

## Implementation order

1. ES mapping + ingestion changes (sections 1a, 1b) — entity data flows to ES
2. Migration V13 + percolator changes (4a, 4b) — alerts linked to entities
3. Backend model/API changes (2a, 3a, 3b, 3d, 4c) — expose entity data via API
4. Frontend changes (2b, 3c, 3d, 4d) — clickable entities, entity detail enrichment
5. Agent tooling (5a–5d) — entity lookup tool + alert_lookup enhancement
6. Test end-to-end with alice@example.com test data

## Verification

1. Run V13/V14 migrations
2. Update ES index template, create a new index to pick up mapping
3. Send test message through pipeline → verify ES doc has `entity_id` on participant
4. Create an alert rule that matches → verify `alert.alert_entities` is populated
5. Open message in UI → verify participant is clickable, links to entity page
6. Open entity detail page → verify Messages and Alerts sections show data
7. In agent playground, ask "find all alerts for entities in department X" → verify entity_lookup and alert_lookup work together
8. Run tests: `pytest ingestion-api/tests/ ui/backend/tests/ agents/tests/ -v`
