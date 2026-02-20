# Entity Resolution System — Design Plan

## Context

Umbrella captures communications (email, Teams, Bloomberg, turrets) and normalizes them into a canonical schema. Currently, participants are stored with raw identifiers (email addresses, chat IDs) but there's no way to map these to known entities (people, organizations). Compliance teams need to know *who* is communicating, not just *which handle* was used.

This plan adds an entity resolution system that:
1. Maintains a registry of entities with their handles and attributes
2. Resolves participant handles to entity IDs inline during ingestion
3. Provides CRUD + batch upload via UI and backend API

---

## Data Model

### New PostgreSQL schema: `entity`

#### `entity.entities`

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK, DEFAULT gen_random_uuid() |
| `display_name` | TEXT | NOT NULL |
| `entity_type` | TEXT | NOT NULL — `'person'`, `'organization'`, `'distribution_list'` |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT now() |
| `updated_at` | TIMESTAMPTZ | NOT NULL DEFAULT now() |
| `created_by` | UUID | FK → iam.users(id) |

UNIQUE constraint on `(display_name, entity_type)` to prevent obvious duplicates.

#### `entity.handles`

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK, DEFAULT gen_random_uuid() |
| `entity_id` | UUID | FK → entity.entities(id) ON DELETE CASCADE |
| `handle_type` | TEXT | NOT NULL — `'email'`, `'teams_id'`, `'bloomberg_uuid'`, `'turret_extension'` |
| `handle_value` | TEXT | NOT NULL — normalized (lowercased for email) |
| `is_primary` | BOOLEAN | NOT NULL DEFAULT false |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT now() |

UNIQUE constraint on `(handle_type, handle_value)` — one handle maps to exactly one entity.

#### `entity.attributes`

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK, DEFAULT gen_random_uuid() |
| `entity_id` | UUID | FK → entity.entities(id) ON DELETE CASCADE |
| `attr_key` | TEXT | NOT NULL — `'company'`, `'department'`, `'title'`, `'street'`, `'city'` |
| `attr_value` | TEXT | NOT NULL |
| `valid_from` | TIMESTAMPTZ | optional temporal validity |
| `valid_to` | TIMESTAMPTZ | optional temporal validity |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT now() |

UNIQUE constraint on `(entity_id, attr_key, valid_from)` — one value per key per time period.

### Indexes

- `entity.handles(handle_type, handle_value)` — B-tree, primary resolution lookup
- `entity.handles(entity_id)` — reverse lookups
- `entity.attributes(entity_id)` — fetch all attributes for an entity
- `entity.entities(entity_type)` — filtering

### DB Role

`entity_rw` — USAGE on `entity` schema, full CRUD on all three tables.

---

## Schema Changes (NormalizedMessage)

Extend the `Participant` model in `connectors/connector-framework/umbrella_schema/normalized_message.py`:

```python
class Participant(BaseModel):
    id: str                        # handle value (email, chat ID)
    name: str                      # display name
    role: str                      # sender, to, cc, bcc, participant
    entity_id: str | None = None   # resolved entity UUID, None if unresolved
    entity_name: str | None = None # resolved entity display name
```

These optional fields are populated by the resolution step. Downstream consumers (Elasticsearch, Logstash, UI) can use `entity_id` for grouping and filtering.

---

## Resolution Service (In-Pipeline)

### Architecture

Synchronous inline resolution with an in-memory cache, integrated into the ingestion pipeline:

```
ParsedMessage → Normalizer → NormalizedMessage → EntityResolver.resolve() → enriched NormalizedMessage → dual-write (Kafka + S3)
```

### Component: `EntityResolver`

**Location:** `ingestion-api/umbrella_ingestion/resolver.py`

```python
class EntityResolver:
    async def start(self):
        """Load initial handle→entity cache from Postgres, start periodic refresh task."""

    async def stop(self):
        """Cancel refresh task, close DB connection."""

    async def resolve(self, message: NormalizedMessage) -> NormalizedMessage:
        """For each participant, look up handle in cache, set entity_id and entity_name."""
        for participant in message.participants:
            handle_key = self._normalize_handle(participant.id, message.channel)
            entity = self._cache.get(handle_key)
            if entity:
                participant.entity_id = entity.id
                participant.entity_name = entity.display_name
        return message

    def _normalize_handle(self, handle: str, channel: Channel) -> tuple[str, str]:
        """Normalize handle value and infer handle_type from channel.
        - email: lowercase, strip whitespace
        - teams_id: lowercase
        - bloomberg_uuid: as-is
        - turret_extension: strip whitespace
        Returns (handle_type, normalized_handle_value)."""
```

### Cache Strategy

- **Startup**: Load full `(handle_type, handle_value) → (entity_id, display_name)` map from Postgres into a Python dict
- **Refresh**: Every N seconds (configurable via `ENTITY_RESOLVER_CACHE_REFRESH_SECONDS`, default 60), reload the full map in a background asyncio task
- **Size estimate**: ~20MB for 100K handles — acceptable for a single service instance
- **Future**: If handle count exceeds ~1M, consider adding Redis as a caching layer

### Integration Point

In `IngestionService.run()` (`ingestion-api/umbrella_ingestion/service.py`):

```python
# After normalization, before dual-write:
normalized = normalizer.normalize(raw_message)
normalized = await self._resolver.resolve(normalized)  # <-- NEW
await self._dual_write(normalized)
```

The resolver is initialized alongside the ingestion service and shares its lifecycle (start/stop).

---

## Backend API (FastAPI)

### New Files

| File | Purpose |
|------|---------|
| `ui/backend/umbrella_ui/db/models/entity.py` | SQLAlchemy v2 ORM models |
| `ui/backend/umbrella_ui/schemas/entity.py` | Pydantic v2 request/response schemas |
| `ui/backend/umbrella_ui/routers/entities.py` | FastAPI router |

### Config Changes

- `ui/backend/umbrella_ui/config.py` — add `UMBRELLA_UI_ENTITY_DATABASE_URL`
- `ui/backend/umbrella_ui/deps.py` — add `get_entity_session()` dependency

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/entities` | List entities (paginated, filterable by type, searchable by name) |
| `POST` | `/api/v1/entities` | Create entity with handles + attributes |
| `GET` | `/api/v1/entities/{id}` | Get entity with all handles + attributes |
| `PATCH` | `/api/v1/entities/{id}` | Update entity fields |
| `DELETE` | `/api/v1/entities/{id}` | Delete entity (cascades to handles/attributes) |
| `POST` | `/api/v1/entities/{id}/handles` | Add handle to entity |
| `DELETE` | `/api/v1/entities/{id}/handles/{handle_id}` | Remove handle |
| `POST` | `/api/v1/entities/{id}/attributes` | Add/update attribute |
| `DELETE` | `/api/v1/entities/{id}/attributes/{attr_id}` | Remove attribute |
| `POST` | `/api/v1/entities/batch` | Batch upload (CSV or JSON) |

### Batch Upload

**JSON format:**
```json
[
  {
    "display_name": "Jane Smith",
    "entity_type": "person",
    "handles": [
      {"handle_type": "email", "handle_value": "jane.smith@acme.com", "is_primary": true},
      {"handle_type": "teams_id", "handle_value": "jane.smith@acme.onmicrosoft.com"}
    ],
    "attributes": [
      {"attr_key": "company", "attr_value": "Acme Corp"},
      {"attr_key": "department", "attr_value": "Trading"}
    ]
  }
]
```

**CSV format:**
```csv
display_name,entity_type,handle_type,handle_value,is_primary,company,department
Jane Smith,person,email,jane.smith@acme.com,true,Acme Corp,Trading
Jane Smith,person,teams_id,jane.smith@acme.onmicrosoft.com,false,,
```

Rows with the same `display_name + entity_type` are merged into one entity. Non-handle columns become attributes (empty values are skipped).

---

## Frontend (React + TypeScript)

### New Files

| File | Purpose |
|------|---------|
| `ui/frontend/src/api/entities.ts` | API client functions |
| `ui/frontend/src/hooks/useEntities.ts` | React Query hooks (useEntities, useEntity, useCreateEntity, etc.) |
| `ui/frontend/src/pages/EntitiesPage.tsx` | List page with search, filter by type, pagination |
| `ui/frontend/src/pages/EntityDetailPage.tsx` | Detail view with handle/attribute management |
| `ui/frontend/src/components/entities/EntityTable.tsx` | Data table component |
| `ui/frontend/src/components/entities/EntityForm.tsx` | Create/edit dialog |
| `ui/frontend/src/components/entities/BatchUploadDialog.tsx` | File upload for CSV/JSON batch import |

### Routes

Add to `ui/frontend/src/App.tsx`:
```
/entities          → EntitiesPage
/entities/:id      → EntityDetailPage
```

### Navigation

Add "Entities" to the sidebar navigation.

### Type Definitions

Add to `ui/frontend/src/lib/types.ts`:
```typescript
interface EntityOut {
  id: string;
  display_name: string;
  entity_type: string;
  handles: HandleOut[];
  attributes: AttributeOut[];
  created_at: string;
  updated_at: string;
}

interface HandleOut {
  id: string;
  handle_type: string;
  handle_value: string;
  is_primary: boolean;
}

interface AttributeOut {
  id: string;
  attr_key: string;
  attr_value: string;
  valid_from: string | null;
  valid_to: string | null;
}
```

---

## Migration

**File:** `infrastructure/postgresql/migrations/V7__entity_resolution.sql`

Creates:
1. `entity` schema
2. `entity_rw` role with appropriate grants
3. All three tables (`entities`, `handles`, `attributes`) with indexes and constraints
4. Foreign key from `entities.created_by` to `iam.users(id)`

---

## K8s / Config Changes

- Add `UMBRELLA_UI_ENTITY_DATABASE_URL` to backend deployment secret
- Add `ENTITY_DB_*` env vars to ingestion service deployment (for resolver Postgres connection)
- Add `ENTITY_RESOLVER_CACHE_REFRESH_SECONDS` (default: 60) to ingestion config

---

## Implementation Order

1. **Migration** — `V7__entity_resolution.sql`
2. **Schema update** — Add `entity_id`, `entity_name` to `Participant` model
3. **Backend API** — SQLAlchemy models, Pydantic schemas, FastAPI router, deps
4. **Resolver** — `EntityResolver` class + integration into `IngestionService`
5. **Frontend** — Entity management pages + batch upload
6. **Tests** — Unit tests for resolver, API endpoints, frontend components

## Verification

1. Run migration, verify tables with `\dt entity.*`
2. Create entity via `POST /api/v1/entities`, verify in DB
3. Batch upload via `POST /api/v1/entities/batch`, verify multiple entities created
4. Send test message through pipeline, verify `entity_id` populated on matching participants
5. Update entity handle, wait for cache refresh, verify new handle resolves
6. Navigate to `/entities` in UI, create/edit/delete entities, upload batch file
7. Run tests: `pytest ingestion-api/tests/ ui/backend/tests/ -v`
