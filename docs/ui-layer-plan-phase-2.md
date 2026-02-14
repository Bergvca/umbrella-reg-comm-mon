# UI Layer — Phase 2 Detailed Implementation Plan

**Goal:** Alert review workflow, message search, queue management, and decision submission — all backed by Elasticsearch integration and the remaining PostgreSQL schemas (`policy`, `alert`, `review`).

**Outcome:** A reviewer can log in, list alerts (hybrid PG + ES query), view an alert's linked ES message, submit a decision, and see the audit trail. A supervisor can create queues, assign batches to reviewers, and view all review activity.

---

## Prerequisites

- Phase 1 completed and tests passing (`uv run pytest ui/backend/tests/ -v`)
- PostgreSQL running with migrations V1–V6 applied
- Elasticsearch running with `messages-*` and `alerts-*` index templates applied
- The `umbrella-ui-backend` package installed in editable mode

---

## Step 1: Add `elasticsearch[async]` and `boto3` to dependencies

**File:** `ui/backend/pyproject.toml`

Add two new dependencies to the existing `dependencies` list:

```toml
    "elasticsearch[async]>=8.0,<9.0",
    "boto3>=1.35",
```

After editing, reinstall:

```bash
uv pip install -e ui/backend/
```

---

## Step 2: Add Elasticsearch and S3 settings to `config.py`

**File:** `ui/backend/umbrella_ui/config.py`

Add these fields to the existing `Settings` class, after the JWT section:

```python
    # --- Elasticsearch ---------------------------------------------------
    elasticsearch_url: str = Field(
        default="http://localhost:9200",
        description="Elasticsearch base URL",
    )

    # --- S3 / MinIO ------------------------------------------------------
    s3_endpoint_url: str = Field(
        default="http://localhost:9000",
        description="S3-compatible endpoint URL",
    )
    s3_bucket: str = Field(
        default="umbrella",
        description="S3 bucket name for attachments and audio",
    )
    s3_region: str = Field(
        default="us-east-1",
        description="S3 region",
    )
    s3_presigned_url_expiry: int = Field(
        default=3600,
        description="Pre-signed URL expiry in seconds",
    )
```

---

## Step 3: Create the Elasticsearch client wrapper

**File:** `ui/backend/umbrella_ui/es/__init__.py` — empty

**File:** `ui/backend/umbrella_ui/es/client.py`

```python
"""Async Elasticsearch client wrapper."""

from __future__ import annotations

from elasticsearch import AsyncElasticsearch

from umbrella_ui.config import Settings


class ESClient:
    """Wraps the async Elasticsearch client.

    Created once at startup and stored on ``app.state``.
    """

    def __init__(self, settings: Settings) -> None:
        self._client = AsyncElasticsearch(
            hosts=[settings.elasticsearch_url],
            request_timeout=30,
        )

    @property
    def client(self) -> AsyncElasticsearch:
        return self._client

    async def close(self) -> None:
        await self._client.close()
```

---

## Step 4: Create ES query builders

**File:** `ui/backend/umbrella_ui/es/queries.py`

This module contains functions that build Elasticsearch query dicts. Each function takes typed parameters and returns a dict suitable for passing to `es.search(body=...)`. The routers call these builders — they never construct raw ES queries inline.

```python
"""Elasticsearch query builders for messages and alerts."""

from __future__ import annotations

from datetime import datetime


def build_message_search(
    *,
    q: str | None = None,
    channel: str | None = None,
    direction: str | None = None,
    participant: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    sentiment: str | None = None,
    risk_score_min: float | None = None,
    offset: int = 0,
    limit: int = 20,
) -> dict:
    """Build an ES query for ``messages-*``.

    Returns a dict ready to pass as ``body=`` to ``AsyncElasticsearch.search()``.
    """
    must: list[dict] = []
    filters: list[dict] = []

    if q:
        must.append({
            "multi_match": {
                "query": q,
                "fields": ["body_text", "transcript", "translated_text"],
                "type": "best_fields",
            }
        })

    if channel:
        filters.append({"term": {"channel": channel}})

    if direction:
        filters.append({"term": {"direction": direction}})

    if participant:
        filters.append({
            "nested": {
                "path": "participants",
                "query": {
                    "multi_match": {
                        "query": participant,
                        "fields": ["participants.name", "participants.id"],
                    }
                },
            }
        })

    if date_from or date_to:
        range_q: dict = {}
        if date_from:
            range_q["gte"] = date_from.isoformat()
        if date_to:
            range_q["lte"] = date_to.isoformat()
        filters.append({"range": {"timestamp": range_q}})

    if sentiment:
        filters.append({"term": {"sentiment": sentiment}})

    if risk_score_min is not None:
        filters.append({"range": {"risk_score": {"gte": risk_score_min}}})

    body: dict = {
        "query": {
            "bool": {
                "must": must or [{"match_all": {}}],
                "filter": filters,
            }
        },
        "highlight": {
            "fields": {
                "body_text": {},
                "transcript": {},
                "translated_text": {},
            }
        },
        "sort": [{"timestamp": {"order": "desc"}}],
        "from": offset,
        "size": limit,
    }

    return body


def build_alert_stats() -> dict:
    """Build an ES aggregation query for ``alerts-*`` dashboard stats."""
    return {
        "size": 0,
        "aggs": {
            "by_severity": {"terms": {"field": "severity"}},
            "by_channel": {"terms": {"field": "channel"}},
            "by_status": {"terms": {"field": "review_status"}},
            "over_time": {
                "date_histogram": {
                    "field": "timestamp",
                    "calendar_interval": "day",
                }
            },
        },
    }


def build_batch_fetch_messages(es_refs: list[dict]) -> dict:
    """Build a multi-get-style bool query to fetch messages by (index, doc_id) pairs.

    ``es_refs`` is a list of ``{"es_index": "...", "es_document_id": "..."}``.

    Uses a ``terms`` query on ``message_id`` across all relevant indices.
    Returns a query body suitable for ``es.search()``.
    """
    doc_ids = [ref["es_document_id"] for ref in es_refs]
    return {
        "query": {
            "terms": {"message_id": doc_ids}
        },
        "size": len(doc_ids),
    }
```

---

## Step 5: Create ES Pydantic response models

**File:** `ui/backend/umbrella_ui/es/models.py`

These models represent the data returned from Elasticsearch and are used to build API responses. They mirror the ES index mappings.

```python
"""Pydantic models for Elasticsearch documents."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ESParticipant(BaseModel):
    id: str
    name: str
    role: str


class ESAttachment(BaseModel):
    name: str
    content_type: str
    s3_uri: str


class ESEntity(BaseModel):
    text: str
    label: str
    start: int | None = None
    end: int | None = None


class ESMessage(BaseModel):
    """A message document from the ``messages-*`` index."""

    message_id: str
    channel: str
    direction: str | None = None
    timestamp: datetime
    participants: list[ESParticipant] = []
    body_text: str | None = None
    audio_ref: str | None = None
    attachments: list[ESAttachment] = []
    transcript: str | None = None
    language: str | None = None
    translated_text: str | None = None
    entities: list[ESEntity] = []
    sentiment: str | None = None
    sentiment_score: float | None = None
    risk_score: float | None = None
    matched_policies: list[str] = []
    processing_status: str | None = None


class ESMessageHit(BaseModel):
    """A single search hit with optional highlights."""

    message: ESMessage
    index: str
    score: float | None = None
    highlights: dict[str, list[str]] = {}


class ESAlert(BaseModel):
    """An alert document from the ``alerts-*`` index."""

    alert_id: str
    message_id: str | None = None
    channel: str | None = None
    timestamp: datetime | None = None
    alert_type: str | None = None
    severity: str | None = None
    risk_score: float | None = None
    matched_policies: list[str] = []
    matched_terms: list[str] = []
    excerpt: str | None = None
    participants: list[ESParticipant] = []
    review_status: str | None = None


class AlertStatsBucket(BaseModel):
    key: str
    doc_count: int


class AlertTimePoint(BaseModel):
    key_as_string: str
    doc_count: int


class AlertStats(BaseModel):
    by_severity: list[AlertStatsBucket] = []
    by_channel: list[AlertStatsBucket] = []
    by_status: list[AlertStatsBucket] = []
    over_time: list[AlertTimePoint] = []
```

---

## Step 6: Create SQLAlchemy ORM models for `policy` schema

**File:** `ui/backend/umbrella_ui/db/models/policy.py`

These models MUST exactly mirror `infrastructure/postgresql/migrations/V3__policy.sql`. Use the same `Base` from `iam.py`.

```python
"""SQLAlchemy ORM models for the policy schema."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from umbrella_ui.db.models.iam import Base


class RiskModel(Base):
    __tablename__ = "risk_models"
    __table_args__ = {"schema": "policy"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam.users.id"),
    )
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))

    policies: Mapped[list[Policy]] = relationship(back_populates="risk_model")


class Policy(Base):
    __tablename__ = "policies"
    __table_args__ = {"schema": "policy"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    risk_model_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("policy.risk_models.id", ondelete="RESTRICT"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam.users.id"),
    )
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))

    risk_model: Mapped[RiskModel] = relationship(back_populates="policies")
    rules: Mapped[list[Rule]] = relationship(back_populates="policy")


class Rule(Base):
    __tablename__ = "rules"
    __table_args__ = {"schema": "policy"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    policy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("policy.policies.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    kql: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam.users.id"),
    )
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))

    policy: Mapped[Policy] = relationship(back_populates="rules")


class GroupPolicy(Base):
    __tablename__ = "group_policies"
    __table_args__ = {"schema": "policy"}

    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam.groups.id", ondelete="CASCADE"),
        primary_key=True,
    )
    policy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("policy.policies.id", ondelete="CASCADE"),
        primary_key=True,
    )
    assigned_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam.users.id"),
    )
    assigned_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
```

**Key rules:**
- Every `__table_args__` must include `{"schema": "policy"}`.
- `Rule.severity` has a CHECK constraint in PG (`low`, `medium`, `high`, `critical`) — validation happens at the DB level.
- `GroupPolicy` is a many-to-many join table between `iam.groups` and `policy.policies`.

---

## Step 7: Create SQLAlchemy ORM models for `alert` schema

**File:** `ui/backend/umbrella_ui/db/models/alert.py`

Mirrors `infrastructure/postgresql/migrations/V4__alert.sql`.

```python
"""SQLAlchemy ORM models for the alert schema."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from umbrella_ui.db.models.iam import Base


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = {"schema": "alert"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    rule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("policy.rules.id", ondelete="RESTRICT"),
        nullable=False,
    )
    es_index: Mapped[str] = mapped_column(Text, nullable=False)
    es_document_id: Mapped[str] = mapped_column(Text, nullable=False)
    es_document_ts: Mapped[datetime | None] = mapped_column()
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'open'"))
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
```

---

## Step 8: Create SQLAlchemy ORM models for `review` schema

**File:** `ui/backend/umbrella_ui/db/models/review.py`

Mirrors `infrastructure/postgresql/migrations/V5__review.sql`.

```python
"""SQLAlchemy ORM models for the review schema."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Integer, Text, text
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from umbrella_ui.db.models.iam import Base


class Queue(Base):
    __tablename__ = "queues"
    __table_args__ = {"schema": "review"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    policy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("policy.policies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam.users.id"),
    )
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))

    batches: Mapped[list[QueueBatch]] = relationship(back_populates="queue")


class QueueBatch(Base):
    __tablename__ = "queue_batches"
    __table_args__ = {"schema": "review"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    queue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("review.queues.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str | None] = mapped_column(Text)
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam.users.id", ondelete="SET NULL"),
    )
    assigned_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam.users.id", ondelete="SET NULL"),
    )
    assigned_at: Mapped[datetime | None] = mapped_column()
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"))
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))

    queue: Mapped[Queue] = relationship(back_populates="batches")
    items: Mapped[list[QueueItem]] = relationship(back_populates="batch")


class QueueItem(Base):
    __tablename__ = "queue_items"
    __table_args__ = {"schema": "review"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("review.queue_batches.id", ondelete="CASCADE"),
        nullable=False,
    )
    alert_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("alert.alerts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))

    batch: Mapped[QueueBatch] = relationship(back_populates="items")


class DecisionStatus(Base):
    __tablename__ = "decision_statuses"
    __table_args__ = {"schema": "review"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_terminal: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))


class Decision(Base):
    __tablename__ = "decisions"
    __table_args__ = {"schema": "review"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    alert_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("alert.alerts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    reviewer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam.users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("review.decision_statuses.id", ondelete="RESTRICT"),
        nullable=False,
    )
    comment: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = {"schema": "review"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    decision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("review.decisions.id", ondelete="CASCADE"),
        nullable=False,
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam.users.id"),
    )
    action: Mapped[str] = mapped_column(Text, nullable=False)
    old_values: Mapped[dict | None] = mapped_column(JSONB)
    new_values: Mapped[dict | None] = mapped_column(JSONB)
    occurred_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
    ip_address: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(Text)
```

---

## Step 9: Create Pydantic schemas for alerts, review, and messages

### 9a: Alert schemas

**File:** `ui/backend/umbrella_ui/schemas/alert.py`

```python
"""Request/response schemas for alert endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from umbrella_ui.es.models import ESMessage


class AlertOut(BaseModel):
    """Alert metadata from PostgreSQL."""

    id: UUID
    name: str
    rule_id: UUID
    es_index: str
    es_document_id: str
    es_document_ts: datetime | None
    severity: str
    status: str
    created_at: datetime


class AlertWithMessage(AlertOut):
    """Alert metadata merged with the linked ES message (for detail view)."""

    rule_name: str | None = None
    policy_name: str | None = None
    message: ESMessage | None = None


class AlertStatusUpdate(BaseModel):
    """Request body for PATCH /alerts/{id}/status."""

    status: str  # "open", "in_review", or "closed"


class AlertListParams(BaseModel):
    """Query parameters for GET /alerts."""

    severity: str | None = None
    status: str | None = None
    channel: str | None = None
    rule_id: UUID | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    offset: int = 0
    limit: int = 50
```

### 9b: Review schemas

**File:** `ui/backend/umbrella_ui/schemas/review.py`

```python
"""Request/response schemas for review endpoints (queues, decisions, audit)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


# --- Decision statuses ---

class DecisionStatusOut(BaseModel):
    id: UUID
    name: str
    description: str | None
    is_terminal: bool
    display_order: int
    created_at: datetime


# --- Decisions ---

class DecisionCreate(BaseModel):
    status_id: UUID
    comment: str | None = None


class DecisionOut(BaseModel):
    id: UUID
    alert_id: UUID
    reviewer_id: UUID
    status_id: UUID
    status_name: str | None = None
    comment: str | None
    decided_at: datetime


# --- Queues ---

class QueueCreate(BaseModel):
    name: str
    description: str | None = None
    policy_id: UUID


class QueueOut(BaseModel):
    id: UUID
    name: str
    description: str | None
    policy_id: UUID
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime


class QueueDetail(QueueOut):
    batch_count: int
    total_items: int


# --- Batches ---

class BatchCreate(BaseModel):
    name: str | None = None


class BatchAssign(BaseModel):
    assigned_to: UUID


class BatchStatusUpdate(BaseModel):
    status: str  # "pending", "in_progress", "completed"


class BatchOut(BaseModel):
    id: UUID
    queue_id: UUID
    name: str | None
    assigned_to: UUID | None
    assigned_by: UUID | None
    assigned_at: datetime | None
    status: str
    created_at: datetime
    updated_at: datetime
    item_count: int = 0


# --- Queue items ---

class QueueItemCreate(BaseModel):
    alert_id: UUID
    position: int


class QueueItemOut(BaseModel):
    id: UUID
    batch_id: UUID
    alert_id: UUID
    position: int
    created_at: datetime


# --- Audit log ---

class AuditLogEntry(BaseModel):
    id: UUID
    decision_id: UUID
    actor_id: UUID | None
    action: str
    old_values: dict | None
    new_values: dict | None
    occurred_at: datetime
    ip_address: str | None
    user_agent: str | None
```

### 9c: Message schemas

**File:** `ui/backend/umbrella_ui/schemas/message.py`

```python
"""Request/response schemas for message search endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from umbrella_ui.es.models import ESMessage, ESMessageHit


class MessageSearchParams(BaseModel):
    """Query parameters for GET /messages/search."""

    q: str | None = None
    channel: str | None = None
    direction: str | None = None
    participant: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    sentiment: str | None = None
    risk_score_min: float | None = None
    offset: int = 0
    limit: int = 20


class MessageSearchResponse(BaseModel):
    hits: list[ESMessageHit]
    total: int
    offset: int
    limit: int


class AudioUrlResponse(BaseModel):
    url: str
    expires_in: int
```

---

## Step 10: Register ES client in the app lifespan

**File:** `ui/backend/umbrella_ui/app.py`

Modify the existing `lifespan` function to also create and close the ES client. Add the import at the top of the file:

```python
from umbrella_ui.es.client import ESClient
```

Then update the `lifespan` function body:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: create DB engines + ES client. Shutdown: dispose."""
    settings: Settings = app.state.settings
    db = DatabaseEngines(settings)
    app.state.db = db
    es = ESClient(settings)
    app.state.es = es
    logger.info("database_engines_created")
    logger.info("elasticsearch_client_created")
    yield
    await es.close()
    await db.close()
    logger.info("shutdown_complete")
```

---

## Step 11: Add ES and S3 dependencies to `deps.py`

**File:** `ui/backend/umbrella_ui/deps.py`

Add these functions to the existing file:

```python
from elasticsearch import AsyncElasticsearch

async def get_es(request: Request) -> AsyncElasticsearch:
    return request.app.state.es.client


def get_settings(request: Request) -> Settings:
    from umbrella_ui.config import Settings
    return request.app.state.settings
```

---

## Step 12: Create the Alerts router

**File:** `ui/backend/umbrella_ui/routers/alerts.py`

This is the most complex router — it implements the **hybrid query pattern**: query PostgreSQL for alert metadata, then batch-fetch linked Elasticsearch documents to merge into the response.

| Method | Path | Role | Description |
|---|---|---|---|
| `GET` | `/api/v1/alerts` | reviewer+ | List alerts with PG filters, batch-fetch ES message previews |
| `GET` | `/api/v1/alerts/{id}` | reviewer+ | Alert detail with full linked ES message |
| `PATCH` | `/api/v1/alerts/{id}/status` | reviewer+ | Update alert status |
| `GET` | `/api/v1/alerts/stats` | supervisor+ | ES aggregations for dashboard |

Implementation details:

- **`GET /alerts`** —
  1. Build a SQLAlchemy query on `alert.alerts` with optional filters: `severity`, `status`, `date_from`/`date_to`, `rule_id`.
  2. Paginate with `offset`/`limit`. Get total count.
  3. For the page of alerts, collect their `es_index` + `es_document_id` pairs.
  4. Call `es.search(index="messages-*", body=build_batch_fetch_messages(refs))` to get the linked messages.
  5. Build a lookup dict `{doc_id: ESMessage}` and merge into the response.
  6. Return `PaginatedResponse[AlertOut]` where each item includes a truncated message excerpt.

- **`GET /alerts/{id}`** —
  1. Query PG for the alert. Join to `policy.rules` and `policy.policies` to get `rule_name` and `policy_name`.
  2. Fetch the single ES document: `es.get(index=alert.es_index, id=alert.es_document_id)`.
  3. Return `AlertWithMessage`.

- **`PATCH /alerts/{id}/status`** —
  1. Validate that status is one of `"open"`, `"in_review"`, `"closed"`.
  2. Update `alert.status` in PG.
  3. Return the updated alert.

- **`GET /alerts/stats`** —
  1. Call `es.search(index="alerts-*", body=build_alert_stats())`.
  2. Parse aggregation buckets into `AlertStats`.
  3. Return the stats.

- Use `Depends(get_alert_session)` for PG queries (the `alert_rw` role can read `alert`, `policy`, and `iam` schemas).
- Use `Depends(get_es)` for ES queries.
- Use `Depends(require_role("reviewer"))` for all endpoints except `/stats` which needs `Depends(require_role("supervisor"))`.

---

## Step 13: Create the Messages router

**File:** `ui/backend/umbrella_ui/routers/messages.py`

| Method | Path | Role | Description |
|---|---|---|---|
| `GET` | `/api/v1/messages/search` | reviewer+ | Full-text search over `messages-*` |
| `GET` | `/api/v1/messages/{index}/{doc_id}` | reviewer+ | Fetch single message from ES |
| `GET` | `/api/v1/messages/{index}/{doc_id}/audio` | reviewer+ | Generate pre-signed S3 URL for audio playback |

Implementation details:

- **`GET /messages/search`** —
  1. Accept query params matching `MessageSearchParams`.
  2. Call `build_message_search(...)` from `es/queries.py`.
  3. Execute `es.search(index="messages-*", body=query)`.
  4. Parse hits into `ESMessageHit` objects, extracting `_source`, `_index`, `_score`, and `highlight`.
  5. Return `MessageSearchResponse`.

- **`GET /messages/{index}/{doc_id}`** —
  1. Call `es.get(index=index, id=doc_id)`.
  2. Parse `_source` into `ESMessage`.
  3. Return the message.
  4. If not found, return 404.

- **`GET /messages/{index}/{doc_id}/audio`** —
  1. Fetch the message from ES.
  2. Check `audio_ref` is not None; if None, return 404.
  3. Parse the S3 URI from `audio_ref` (format: `s3://bucket/key`).
  4. Use `boto3` to generate a pre-signed GET URL with expiry from settings.
  5. Return `AudioUrlResponse`.

- Use `Depends(require_role("reviewer"))` for all endpoints.
- Use `Depends(get_es)` for ES queries.
- Use `Depends(get_settings)` for S3 config.

For the S3 pre-signed URL generation, create a small helper:

```python
import boto3
from umbrella_ui.config import Settings

def generate_presigned_url(s3_uri: str, settings: Settings) -> str:
    """Parse ``s3://bucket/key`` and return a pre-signed GET URL."""
    # Strip "s3://" prefix
    path = s3_uri.removeprefix("s3://")
    bucket, _, key = path.partition("/")
    s3_client = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        region_name=settings.s3_region,
    )
    return s3_client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=settings.s3_presigned_url_expiry,
    )
```

Put this function directly in `routers/messages.py` — it doesn't need its own module.

---

## Step 14: Create the Decisions router

**File:** `ui/backend/umbrella_ui/routers/decisions.py`

| Method | Path | Role | Description |
|---|---|---|---|
| `POST` | `/api/v1/alerts/{alert_id}/decisions` | reviewer+ | Submit a decision on an alert |
| `GET` | `/api/v1/alerts/{alert_id}/decisions` | reviewer+ | List decision history for an alert |
| `GET` | `/api/v1/decision-statuses` | reviewer+ | List available decision statuses |

Implementation details:

- **`POST /alerts/{alert_id}/decisions`** —
  1. Verify the alert exists (query `alert.alerts` via `alert_rw` session).
  2. Verify the `status_id` exists in `review.decision_statuses` (query via `review_rw` session).
  3. Create a `review.decisions` row with `reviewer_id` = current user's ID.
  4. Create a `review.audit_log` row with `action = 'created'`, `new_values` = JSON snapshot of the decision, `actor_id` = current user.
  5. If the decision status has `is_terminal = true`, update `alert.alerts.status = 'closed'` (via the `alert_rw` session).
  6. Commit both sessions.
  7. Return `DecisionOut` with status 201.

  **Important — cross-schema writes:** This endpoint writes to TWO schemas:
  - `review` schema (decision + audit_log) — use `get_review_session`
  - `alert` schema (close alert) — use `get_alert_session`

  The `review_rw` role can READ `alert` but cannot WRITE to it. So when closing an alert, you MUST use the `alert_rw` session. Do NOT try to update `alert.alerts` through the review session.

- **`GET /alerts/{alert_id}/decisions`** —
  1. Query `review.decisions` filtered by `alert_id`, ordered by `decided_at DESC`.
  2. Join to `review.decision_statuses` to include `status_name` in the response.
  3. Return `list[DecisionOut]`.
  4. Use `get_review_session` (the `review_rw` role can read `alert`, `iam`, and `review`).

- **`GET /decision-statuses`** —
  1. Query `review.decision_statuses`, ordered by `display_order`.
  2. Return `list[DecisionStatusOut]`.

---

## Step 15: Create the Queues router

**File:** `ui/backend/umbrella_ui/routers/queues.py`

| Method | Path | Role | Description |
|---|---|---|---|
| `GET` | `/api/v1/queues` | supervisor+ | List all review queues |
| `POST` | `/api/v1/queues` | supervisor+ | Create a queue |
| `GET` | `/api/v1/queues/{id}` | reviewer+ | Queue detail with batch summary |
| `POST` | `/api/v1/queues/{id}/batches` | supervisor+ | Create a batch within a queue |
| `PATCH` | `/api/v1/queues/{id}/batches/{batch_id}` | supervisor+ | Assign batch to reviewer or update status |
| `GET` | `/api/v1/queues/{id}/batches/{batch_id}/items` | reviewer+ | List items in a batch |
| `POST` | `/api/v1/queues/{id}/batches/{batch_id}/items` | supervisor+ | Add an alert to a batch |
| `GET` | `/api/v1/my-queue` | reviewer+ | Get current user's assigned batches |

Implementation details:

- **`POST /queues`** — insert into `review.queues` with `policy_id` and `created_by = current_user.id`. Use `get_review_session`.
- **`GET /queues/{id}`** — return `QueueDetail` including `batch_count` (count of batches) and `total_items` (count of all items across batches).
- **`POST /queues/{id}/batches`** — insert into `review.queue_batches` with `queue_id`.
- **`PATCH /queues/{id}/batches/{batch_id}`** — accept `BatchAssign` or `BatchStatusUpdate`. If assigning, set `assigned_to`, `assigned_by`, `assigned_at = now()`. If updating status, set `status`. Both update `updated_at`.
- **`POST /queues/{id}/batches/{batch_id}/items`** — accept `QueueItemCreate`, insert into `review.queue_items`. Validate that the alert exists (read via `review_rw` session which can read `alert`).
- **`GET /my-queue`** — query `review.queue_batches` where `assigned_to = current_user.id` and `status != 'completed'`. Join to `review.queues` for queue name. Return `list[BatchOut]` with `item_count`.

- Use `get_review_session` for all endpoints. The `review_rw` role can read `policy` and `alert` schemas needed for joins/validation.

---

## Step 16: Create the Audit Log router

**File:** `ui/backend/umbrella_ui/routers/audit.py`

| Method | Path | Role | Description |
|---|---|---|---|
| `GET` | `/api/v1/audit-log` | supervisor+ | Read-only paginated audit log |

Implementation details:

- Accept query parameters: `actor_id` (UUID, optional), `alert_id` (UUID, optional), `date_from`/`date_to` (datetime, optional), `offset`, `limit`.
- To filter by `alert_id`: join `review.audit_log → review.decisions` and filter `decisions.alert_id`.
- Order by `occurred_at DESC`.
- Return `PaginatedResponse[AuditLogEntry]`.
- Use `get_review_session`.
- Use `Depends(require_role("supervisor"))`.

---

## Step 17: Register new routers in `app.py`

**File:** `ui/backend/umbrella_ui/app.py`

Add these imports inside the `create_app` function (after the existing router imports):

```python
    from umbrella_ui.routers.alerts import router as alerts_router
    from umbrella_ui.routers.messages import router as messages_router
    from umbrella_ui.routers.decisions import router as decisions_router
    from umbrella_ui.routers.queues import router as queues_router
    from umbrella_ui.routers.audit import router as audit_router

    app.include_router(alerts_router)
    app.include_router(messages_router)
    app.include_router(decisions_router)
    app.include_router(queues_router)
    app.include_router(audit_router)
```

---

## Step 18: Create Tests

All tests use the same mocking approach as Phase 1: override `get_*_session` and `get_es` via `app.dependency_overrides`.

### 18a: Update `conftest.py`

**File:** `ui/backend/tests/conftest.py`

Add these helpers to the existing conftest:

```python
from umbrella_ui.deps import get_alert_session, get_review_session, get_es, get_settings


def override_alert_session(app, session):
    async def _get_session():
        yield session
    app.dependency_overrides[get_alert_session] = _get_session


def override_review_session(app, session):
    async def _get_session():
        yield session
    app.dependency_overrides[get_review_session] = _get_session


def override_es(app, es_mock):
    def _get_es():
        return es_mock
    app.dependency_overrides[get_es] = _get_es


def make_supervisor_headers(settings, user_id=None):
    uid = user_id or uuid.uuid4()
    token = create_access_token(uid, ["supervisor"], settings)
    return {"Authorization": f"Bearer {token}"}
```

### 18b: Alert tests

**File:** `ui/backend/tests/test_alerts.py`

| Test | What it verifies |
|---|---|
| `test_list_alerts` | GET /alerts → 200, returns paginated list |
| `test_list_alerts_filter_by_severity` | GET /alerts?severity=high → only returns high-severity alerts |
| `test_get_alert_detail` | GET /alerts/{id} → 200, includes linked ES message |
| `test_get_alert_not_found` | GET /alerts/{id} for non-existent alert → 404 |
| `test_update_alert_status` | PATCH /alerts/{id}/status → 200, status updated |
| `test_update_alert_invalid_status` | PATCH with invalid status → 422 |
| `test_alert_stats` | GET /alerts/stats → 200, returns aggregation buckets |
| `test_reviewer_can_list_alerts` | reviewer role → 200 (not just admin) |

Testing approach:
- Mock the PG session to return fake `Alert` objects (MagicMock with correct attributes).
- Mock the ES client (`AsyncMock`) to return fake search responses matching the ES response format: `{"hits": {"total": {"value": N}, "hits": [{"_source": {...}, "_index": "...", "_id": "..."}]}}`.
- Override both `get_alert_session` and `get_es` via `app.dependency_overrides`.

### 18c: Decision tests

**File:** `ui/backend/tests/test_decisions.py`

| Test | What it verifies |
|---|---|
| `test_create_decision` | POST /alerts/{id}/decisions → 201, returns decision |
| `test_create_terminal_decision_closes_alert` | Terminal decision status → alert.status becomes 'closed' |
| `test_create_decision_alert_not_found` | Non-existent alert_id → 404 |
| `test_list_decisions` | GET /alerts/{id}/decisions → 200, returns list ordered by decided_at |
| `test_list_decision_statuses` | GET /decision-statuses → 200, returns all statuses ordered by display_order |

Testing approach:
- Override both `get_review_session` and `get_alert_session` (the decision endpoint writes to both schemas).
- For the terminal decision test, verify that the alert session's commit was called after updating the alert status.

### 18d: Message search tests

**File:** `ui/backend/tests/test_messages.py`

| Test | What it verifies |
|---|---|
| `test_search_messages` | GET /messages/search?q=hello → 200, returns hits with highlights |
| `test_search_messages_with_filters` | channel + date_from + date_to → correct ES query filters applied |
| `test_get_single_message` | GET /messages/{index}/{doc_id} → 200, returns full message |
| `test_get_message_not_found` | Non-existent doc → 404 |
| `test_get_audio_url` | GET /messages/{index}/{doc_id}/audio → 200, returns pre-signed URL |
| `test_get_audio_url_no_audio` | Message without audio_ref → 404 |

Testing approach:
- Mock ES client to return realistic search response dicts.
- Mock `boto3.client` for the audio URL test to return a known URL.

### 18e: Queue tests

**File:** `ui/backend/tests/test_queues.py`

| Test | What it verifies |
|---|---|
| `test_create_queue` | POST /queues → 201 (supervisor) |
| `test_list_queues` | GET /queues → 200, paginated |
| `test_create_batch` | POST /queues/{id}/batches → 201 |
| `test_assign_batch` | PATCH /queues/{id}/batches/{id} → 200, assigned_to set |
| `test_add_item_to_batch` | POST /queues/{id}/batches/{id}/items → 201 |
| `test_list_batch_items` | GET /queues/{id}/batches/{id}/items → 200 |
| `test_my_queue` | GET /my-queue → returns only current user's batches |
| `test_reviewer_cannot_create_queue` | reviewer → 403 |

### 18f: ES query builder tests

**File:** `ui/backend/tests/test_es_queries.py`

These are pure unit tests — no HTTP client needed. They test that the query builder functions produce the correct ES query dicts.

| Test | What it verifies |
|---|---|
| `test_build_message_search_basic` | `q="hello"` → multi_match in must |
| `test_build_message_search_with_channel` | `channel="email"` → term filter |
| `test_build_message_search_with_date_range` | `date_from` + `date_to` → range filter |
| `test_build_message_search_with_participant` | `participant="alice"` → nested query |
| `test_build_message_search_empty` | No params → match_all |
| `test_build_alert_stats` | Returns aggregation query |
| `test_build_batch_fetch_messages` | List of refs → terms query on message_id |

---

## Step 19: Run Tests

```bash
# Install new test dependencies if needed
uv pip install "elasticsearch[async]>=8.0,<9.0" boto3

# Run all tests (Phase 1 + Phase 2)
uv run pytest ui/backend/tests/ -v
```

---

## File Checklist

Every NEW file that Phase 2 must produce (in addition to Phase 1's files):

| # | File | Type |
|---|---|---|
| 1 | `ui/backend/umbrella_ui/es/__init__.py` | empty |
| 2 | `ui/backend/umbrella_ui/es/client.py` | ES client wrapper |
| 3 | `ui/backend/umbrella_ui/es/queries.py` | ES query builders |
| 4 | `ui/backend/umbrella_ui/es/models.py` | ES Pydantic models |
| 5 | `ui/backend/umbrella_ui/db/models/policy.py` | ORM: RiskModel, Policy, Rule, GroupPolicy |
| 6 | `ui/backend/umbrella_ui/db/models/alert.py` | ORM: Alert |
| 7 | `ui/backend/umbrella_ui/db/models/review.py` | ORM: Queue, Batch, Item, DecisionStatus, Decision, AuditLog |
| 8 | `ui/backend/umbrella_ui/schemas/alert.py` | Alert schemas |
| 9 | `ui/backend/umbrella_ui/schemas/review.py` | Review schemas |
| 10 | `ui/backend/umbrella_ui/schemas/message.py` | Message search schemas |
| 11 | `ui/backend/umbrella_ui/routers/alerts.py` | Alert endpoints |
| 12 | `ui/backend/umbrella_ui/routers/messages.py` | Message search endpoints |
| 13 | `ui/backend/umbrella_ui/routers/decisions.py` | Decision endpoints |
| 14 | `ui/backend/umbrella_ui/routers/queues.py` | Queue management endpoints |
| 15 | `ui/backend/umbrella_ui/routers/audit.py` | Audit log endpoint |
| 16 | `ui/backend/tests/test_alerts.py` | Alert tests |
| 17 | `ui/backend/tests/test_decisions.py` | Decision tests |
| 18 | `ui/backend/tests/test_messages.py` | Message search tests |
| 19 | `ui/backend/tests/test_queues.py` | Queue tests |
| 20 | `ui/backend/tests/test_es_queries.py` | ES query builder unit tests |

Files MODIFIED from Phase 1:

| File | Change |
|---|---|
| `ui/backend/pyproject.toml` | Add `elasticsearch[async]` and `boto3` deps |
| `ui/backend/umbrella_ui/config.py` | Add ES and S3 settings |
| `ui/backend/umbrella_ui/app.py` | Create/close ES client in lifespan; register 5 new routers |
| `ui/backend/umbrella_ui/deps.py` | Add `get_es`, `get_settings` |
| `ui/backend/tests/conftest.py` | Add `override_alert_session`, `override_review_session`, `override_es`, `make_supervisor_headers` |

---

## Important Cross-Schema Access Rules

This is critical for the implementation. Each PG session uses a different database role with different privileges:

| Session dependency | DB role | Can READ | Can WRITE |
|---|---|---|---|
| `get_iam_session` | `iam_rw` | `iam` | `iam` |
| `get_policy_session` | `policy_rw` | `iam`, `policy` | `policy` |
| `get_alert_session` | `alert_rw` | `iam`, `policy`, `alert` | `alert` |
| `get_review_session` | `review_rw` | `iam`, `policy`, `alert`, `review` | `review` |

**Rules:**
- The alert router reads `alert.alerts` and joins to `policy.rules` + `policy.policies` — use `get_alert_session` (alert_rw can read all three).
- The decision endpoint writes to `review.decisions` AND updates `alert.alerts.status` — it needs BOTH `get_review_session` (for review writes) AND `get_alert_session` (for alert writes).
- The queue router writes to `review.*` and reads `alert.alerts` — use `get_review_session` (review_rw can read alert).
- Never write to a schema that the session's role doesn't have write access to.

---

## What Phase 2 Does NOT Include

- No policy/rule CRUD (Phase 3)
- No group-policy assignment (Phase 3)
- No export endpoints (Phase 3)
- No frontend (Phase 4+)
- No Dockerfile or K8s manifests (Phase 7)
- No SSO/OIDC
