# PostgreSQL — Schema Design Plan

## Overview

Postgres serves as the operational store for the compliance review platform. Elasticsearch holds the raw/normalized communication events; Postgres holds everything that humans act on: who can review, what rules apply, which alerts were raised, and what decisions were made.

---

## Schema Organisation

Split into four schemas by domain:

| Schema | Purpose |
|---|---|
| `iam` | Users, groups, roles, RBAC |
| `policy` | Risk models, policies, KQL rules |
| `alert` | Alerts linked to Elasticsearch events |
| `review` | Decisions, statuses, audit trail |

Each schema is a separate deployment concern — `iam` and `policy` are config-time data; `alert` and `review` are runtime data that grows continuously.

---

## Schema: `iam`

Reviewer accounts and access control.

```
iam.users
  id            uuid PK
  username      text UNIQUE NOT NULL
  email         text UNIQUE NOT NULL
  password_hash text NOT NULL
  is_active     boolean NOT NULL DEFAULT true
  created_at    timestamptz NOT NULL DEFAULT now()
  updated_at    timestamptz NOT NULL DEFAULT now()

iam.roles
  id            uuid PK
  name          text UNIQUE NOT NULL   -- e.g. 'admin', 'reviewer', 'supervisor'
  description   text
  created_at    timestamptz NOT NULL DEFAULT now()

iam.groups
  id            uuid PK
  name          text UNIQUE NOT NULL   -- e.g. 'equities-desk', 'fixed-income'
  description   text
  created_at    timestamptz NOT NULL DEFAULT now()
  updated_at    timestamptz NOT NULL DEFAULT now()

iam.user_groups          -- many-to-many: users belong to groups
  user_id       uuid FK → iam.users.id   ON DELETE CASCADE
  group_id      uuid FK → iam.groups.id  ON DELETE CASCADE
  assigned_by   uuid FK → iam.users.id   (admin who made the assignment)
  assigned_at   timestamptz NOT NULL DEFAULT now()
  PRIMARY KEY (user_id, group_id)

iam.group_roles          -- many-to-many: groups are granted roles
  group_id      uuid FK → iam.groups.id  ON DELETE CASCADE
  role_id       uuid FK → iam.roles.id   ON DELETE CASCADE
  assigned_by   uuid FK → iam.users.id
  assigned_at   timestamptz NOT NULL DEFAULT now()
  PRIMARY KEY (group_id, role_id)
```

**Notes:**
- Roles are assigned to **groups**, not directly to users. A user's effective roles are the union of all roles belonging to every group they are a member of.
- Admins are identified by membership in a group that carries the `admin` role.
- To check whether a user has a role: `user → user_groups → group_roles → roles`.
- Groups serve double duty: they control access (via roles) and scope policy assignment (via `policy.group_policies`).
- Removing a user from all admin-role groups immediately revokes admin access — no per-user role cleanup needed.

---

## Schema: `policy`

Risk models, policies, and KQL rules.

```
policy.risk_models
  id            uuid PK
  name          text UNIQUE NOT NULL    -- e.g. 'Market Abuse', 'Insider Trading'
  description   text
  is_active     boolean NOT NULL DEFAULT true
  created_by    uuid FK → iam.users.id
  created_at    timestamptz NOT NULL DEFAULT now()
  updated_at    timestamptz NOT NULL DEFAULT now()

policy.policies
  id            uuid PK
  risk_model_id uuid FK → policy.risk_models.id  ON DELETE RESTRICT
  name          text NOT NULL
  description   text
  is_active     boolean NOT NULL DEFAULT true
  created_by    uuid FK → iam.users.id
  created_at    timestamptz NOT NULL DEFAULT now()
  updated_at    timestamptz NOT NULL DEFAULT now()
  UNIQUE (risk_model_id, name)

policy.rules
  id            uuid PK
  policy_id     uuid FK → policy.policies.id  ON DELETE CASCADE
  name          text NOT NULL
  description   text
  kql           text NOT NULL             -- KQL expression evaluated against ES documents
  severity      text NOT NULL             -- 'low' | 'medium' | 'high' | 'critical'
  is_active     boolean NOT NULL DEFAULT true
  created_by    uuid FK → iam.users.id
  created_at    timestamptz NOT NULL DEFAULT now()
  updated_at    timestamptz NOT NULL DEFAULT now()

policy.group_policies    -- assign a policy to one or more groups
  group_id      uuid FK → iam.groups.id    ON DELETE CASCADE
  policy_id     uuid FK → policy.policies.id ON DELETE CASCADE
  assigned_by   uuid FK → iam.users.id
  assigned_at   timestamptz NOT NULL DEFAULT now()
  PRIMARY KEY (group_id, policy_id)
```

**Notes:**
- A **risk model** is a named collection of policies (e.g. all policies relevant to "Market Abuse").
- A **policy** is a named collection of rules under one risk model.
- A **rule** is a single KQL expression. When the expression matches an ES document, an alert is generated.
- Policies are assigned to groups; all users in that group are subject to that policy.
- `severity` is stored as a constrained text column (add a `CHECK` constraint); it can be promoted to an enum if the set is fixed.

---

## Schema: `alert`

Alerts raised when KQL rules match Elasticsearch events.

```
alert.alerts
  id                uuid PK
  name              text NOT NULL           -- human-readable alert name, from the rule
  rule_id           uuid FK → policy.rules.id  ON DELETE RESTRICT
  es_index          text NOT NULL           -- e.g. 'messages-2025.06'
  es_document_id    text NOT NULL           -- Elasticsearch _id
  es_document_ts    timestamptz             -- @timestamp from the ES document
  severity          text NOT NULL           -- copied from rule at alert-generation time
  status            text NOT NULL DEFAULT 'open'  -- 'open' | 'in_review' | 'closed'
  created_at        timestamptz NOT NULL DEFAULT now()
  UNIQUE (rule_id, es_document_id)          -- one alert per rule per document
```

**Notes:**
- `(rule_id, es_document_id)` unique constraint prevents duplicate alerts for the same event.
- `es_index` + `es_document_id` together form the canonical reference back to the Elasticsearch document.
- `severity` is denormalised from the rule at alert-creation time so historical alerts retain their original severity even if the rule is later changed.
- `status` is a simple lifecycle field; the full decision history lives in `review.decisions`.

---

## Schema: `review`

Decisions, configurable statuses, review queues, and audit trail.

```
review.queues
  id            uuid PK
  name          text NOT NULL
  description   text
  policy_id     uuid FK → policy.policies.id  ON DELETE RESTRICT
  created_by    uuid FK → iam.users.id
  created_at    timestamptz NOT NULL DEFAULT now()
  updated_at    timestamptz NOT NULL DEFAULT now()

review.queue_batches     -- a queue can be split into batches, each assigned to one reviewer
  id            uuid PK
  queue_id      uuid FK → review.queues.id  ON DELETE CASCADE
  name          text                          -- e.g. 'Batch 1', 'Alice batch'
  assigned_to   uuid FK → iam.users.id  ON DELETE SET NULL  -- NULL = unassigned
  assigned_by   uuid FK → iam.users.id  ON DELETE SET NULL
  assigned_at   timestamptz
  status        text NOT NULL DEFAULT 'pending'  -- 'pending' | 'in_progress' | 'completed'
  created_at    timestamptz NOT NULL DEFAULT now()
  updated_at    timestamptz NOT NULL DEFAULT now()

review.queue_items       -- the individual alerts/events in a batch
  id            uuid PK
  batch_id      uuid FK → review.queue_batches.id  ON DELETE CASCADE
  alert_id      uuid FK → alert.alerts.id           ON DELETE RESTRICT
  position      int NOT NULL                         -- display order within the batch
  created_at    timestamptz NOT NULL DEFAULT now()
  UNIQUE (batch_id, alert_id)                        -- an alert appears once per batch
  UNIQUE (batch_id, position)

review.decision_statuses
  id            uuid PK
  name          text UNIQUE NOT NULL   -- e.g. 'escalated', 'false_positive', 'breach', 'acknowledged'
  description   text
  is_terminal   boolean NOT NULL DEFAULT false  -- if true, closes the alert
  display_order int NOT NULL DEFAULT 0
  created_at    timestamptz NOT NULL DEFAULT now()

review.decisions
  id            uuid PK
  alert_id      uuid FK → alert.alerts.id  ON DELETE RESTRICT
  reviewer_id   uuid FK → iam.users.id     ON DELETE RESTRICT
  status_id     uuid FK → review.decision_statuses.id ON DELETE RESTRICT
  comment       text
  decided_at    timestamptz NOT NULL DEFAULT now()

review.audit_log
  id            uuid PK
  decision_id   uuid FK → review.decisions.id  ON DELETE CASCADE
  actor_id      uuid FK → iam.users.id
  action        text NOT NULL        -- 'created' | 'updated' | 'deleted'
  old_values    jsonb                -- snapshot of the row before change (NULL for creates)
  new_values    jsonb                -- snapshot of the row after change (NULL for deletes)
  occurred_at   timestamptz NOT NULL DEFAULT now()
  ip_address    inet
  user_agent    text
```

**Notes:**
- A **queue** is a named collection of alerts to be reviewed, scoped to one policy. Queues are created manually (by a supervisor) or automatically when a policy run produces alerts.
- A queue is divided into **batches**; if not subdivided, a queue has a single batch. Each batch is assigned to one reviewer (`assigned_to`). Batches can be reassigned — the audit trail captures who changed what.
- **Queue items** are the individual alerts within a batch, ordered by `position`. The same alert can appear in queues from different policies but only once per batch.
- Batch `status` progression: `pending → in_progress → completed`. The queue's own completion state is derived (all batches completed).
- `decision_statuses` is a configuration table, maintained by admins. `is_terminal = true` signals that the alert should be closed when this status is applied.
- Multiple decisions per alert are allowed — reviewers can update their decision and every change is captured in `audit_log`.
- The audit log is append-only; no row in `audit_log` is ever updated or deleted. Enforce this at the application layer (and optionally via a Postgres trigger that raises an exception on UPDATE/DELETE).
- `old_values` / `new_values` stored as JSONB gives flexibility without schema changes as the `decisions` table evolves.

---

## Cross-Schema Dependency Graph

```
iam.roles ──→ iam.group_roles ──→ iam.groups ──→ iam.user_groups ──→ iam.users
                                       │                                  │
                                       ▼                                  │
                              policy.group_policies                       │
                                       │                                  │
                                       ▼                                  │
                               policy.policies ──→ review.queues          │
                                       │                  │               │
                                       ▼                  ▼               │
                                 policy.rules    review.queue_batches ◄───┤ (assigned_to)
                                       │                  │               │
                                       ▼                  ▼               │
                                 alert.alerts ◄── review.queue_items      │
                                       │                                  │
                                       ▼                                  │
                              review.decisions ◄───────────────────────────┘ (reviewer_id)
                                       │
                                       ▼
                              review.audit_log ◄── iam.users (actor_id)
```

A user's effective roles: `iam.users → iam.user_groups → iam.group_roles → iam.roles`

---

## Infrastructure Notes

- Deploy as a StatefulSet in namespace `umbrella-storage` alongside Elasticsearch and MinIO.
- Separate PersistentVolumeClaim for Postgres data (independent of other storage).
- Init container or Kubernetes Job runs `psql` migrations on startup (Flyway or plain SQL files under `infrastructure/postgresql/migrations/`).
- Credentials via Kubernetes Secret; connection string passed to services via env vars (`POSTGRES_*` prefix).
- Separate database roles per schema for least-privilege: `iam_rw`, `policy_rw`, `alert_rw`, `review_rw`.

---

## Files to Create

| File | Purpose |
|---|---|
| `deploy/k8s/umbrella-storage/postgresql/statefulset.yaml` | Postgres StatefulSet + Service |
| `deploy/k8s/umbrella-storage/postgresql/secret.yaml` | Credentials (or External Secret reference) |
| `deploy/k8s/umbrella-storage/postgresql/configmap.yaml` | `postgresql.conf` overrides |
| `infrastructure/postgresql/migrations/V1__schemas.sql` | Create four schemas |
| `infrastructure/postgresql/migrations/V2__iam.sql` | `iam.*` tables |
| `infrastructure/postgresql/migrations/V3__policy.sql` | `policy.*` tables |
| `infrastructure/postgresql/migrations/V4__alert.sql` | `alert.*` tables |
| `infrastructure/postgresql/migrations/V5__review.sql` | `review.*` tables (queues, batches, items, decisions, audit) + audit trigger |
| `infrastructure/postgresql/migrations/V6__seed.sql` | Seed default roles, decision statuses |
| `deploy/k8s/umbrella-storage/postgresql/migration-job.yaml` | K8s Job runs migrations on deploy |
