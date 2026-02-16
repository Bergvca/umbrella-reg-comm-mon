# PostgreSQL Schema Reference

Database: `umbrella`

Four schemas by domain:

| Schema | Purpose |
|---|---|
| `iam` | Users, groups, roles, RBAC |
| `policy` | Risk models, policies, KQL rules |
| `alert` | Alerts linked to Elasticsearch events |
| `review` | Decisions, statuses, review queues, audit trail |

Migrations live in `infrastructure/postgresql/migrations/` (Flyway V-versioned).

---

## Schema: `iam`

### `iam.users`

| Column | Type | Constraints |
|---|---|---|
| `id` | uuid | PK, default `gen_random_uuid()` |
| `username` | text | UNIQUE NOT NULL |
| `email` | text | UNIQUE NOT NULL |
| `password_hash` | text | NOT NULL |
| `is_active` | boolean | NOT NULL DEFAULT true |
| `created_at` | timestamptz | NOT NULL DEFAULT now() |
| `updated_at` | timestamptz | NOT NULL DEFAULT now() |

### `iam.roles`

| Column | Type | Constraints |
|---|---|---|
| `id` | uuid | PK, default `gen_random_uuid()` |
| `name` | text | UNIQUE NOT NULL |
| `description` | text | |
| `created_at` | timestamptz | NOT NULL DEFAULT now() |

Seeded values: `admin`, `supervisor`, `reviewer`

### `iam.groups`

| Column | Type | Constraints |
|---|---|---|
| `id` | uuid | PK, default `gen_random_uuid()` |
| `name` | text | UNIQUE NOT NULL |
| `description` | text | |
| `created_at` | timestamptz | NOT NULL DEFAULT now() |
| `updated_at` | timestamptz | NOT NULL DEFAULT now() |

### `iam.user_groups`

Many-to-many: users belong to groups.

| Column | Type | Constraints |
|---|---|---|
| `user_id` | uuid | PK, FK → `iam.users.id` ON DELETE CASCADE |
| `group_id` | uuid | PK, FK → `iam.groups.id` ON DELETE CASCADE |
| `assigned_by` | uuid | FK → `iam.users.id` |
| `assigned_at` | timestamptz | NOT NULL DEFAULT now() |

Indexes: `(group_id)`

### `iam.group_roles`

Many-to-many: groups are granted roles.

| Column | Type | Constraints |
|---|---|---|
| `group_id` | uuid | PK, FK → `iam.groups.id` ON DELETE CASCADE |
| `role_id` | uuid | PK, FK → `iam.roles.id` ON DELETE CASCADE |
| `assigned_by` | uuid | FK → `iam.users.id` |
| `assigned_at` | timestamptz | NOT NULL DEFAULT now() |

Indexes: `(role_id)`

**Role resolution:** `iam.users → iam.user_groups → iam.group_roles → iam.roles`

---

## Schema: `policy`

### `policy.risk_models`

| Column | Type | Constraints |
|---|---|---|
| `id` | uuid | PK, default `gen_random_uuid()` |
| `name` | text | UNIQUE NOT NULL |
| `description` | text | |
| `is_active` | boolean | NOT NULL DEFAULT true |
| `created_by` | uuid | FK → `iam.users.id` |
| `created_at` | timestamptz | NOT NULL DEFAULT now() |
| `updated_at` | timestamptz | NOT NULL DEFAULT now() |

### `policy.policies`

| Column | Type | Constraints |
|---|---|---|
| `id` | uuid | PK, default `gen_random_uuid()` |
| `risk_model_id` | uuid | NOT NULL, FK → `policy.risk_models.id` ON DELETE RESTRICT |
| `name` | text | NOT NULL |
| `description` | text | |
| `is_active` | boolean | NOT NULL DEFAULT true |
| `created_by` | uuid | FK → `iam.users.id` |
| `created_at` | timestamptz | NOT NULL DEFAULT now() |
| `updated_at` | timestamptz | NOT NULL DEFAULT now() |

Unique: `(risk_model_id, name)` · Indexes: `(risk_model_id)`

### `policy.rules`

| Column | Type | Constraints |
|---|---|---|
| `id` | uuid | PK, default `gen_random_uuid()` |
| `policy_id` | uuid | NOT NULL, FK → `policy.policies.id` ON DELETE CASCADE |
| `name` | text | NOT NULL |
| `description` | text | |
| `kql` | text | NOT NULL — KQL expression evaluated against ES documents |
| `severity` | text | NOT NULL, CHECK IN (`low`, `medium`, `high`, `critical`) |
| `is_active` | boolean | NOT NULL DEFAULT true |
| `created_by` | uuid | FK → `iam.users.id` |
| `created_at` | timestamptz | NOT NULL DEFAULT now() |
| `updated_at` | timestamptz | NOT NULL DEFAULT now() |

Indexes: `(policy_id)`

### `policy.group_policies`

Assigns a policy to one or more groups.

| Column | Type | Constraints |
|---|---|---|
| `group_id` | uuid | PK, FK → `iam.groups.id` ON DELETE CASCADE |
| `policy_id` | uuid | PK, FK → `policy.policies.id` ON DELETE CASCADE |
| `assigned_by` | uuid | FK → `iam.users.id` |
| `assigned_at` | timestamptz | NOT NULL DEFAULT now() |

Indexes: `(policy_id)`

---

## Schema: `alert`

### `alert.alerts`

| Column | Type | Constraints |
|---|---|---|
| `id` | uuid | PK, default `gen_random_uuid()` |
| `name` | text | NOT NULL — human-readable, copied from rule at creation time |
| `rule_id` | uuid | NOT NULL, FK → `policy.rules.id` ON DELETE RESTRICT |
| `es_index` | text | NOT NULL — e.g. `messages-2025.06` |
| `es_document_id` | text | NOT NULL — Elasticsearch `_id` |
| `es_document_ts` | timestamptz | `@timestamp` from the ES document |
| `severity` | text | NOT NULL, CHECK IN (`low`, `medium`, `high`, `critical`) — denormalised from rule at creation time |
| `status` | text | NOT NULL DEFAULT `open`, CHECK IN (`open`, `in_review`, `closed`) |
| `created_at` | timestamptz | NOT NULL DEFAULT now() |

Unique: `(rule_id, es_document_id)` — one alert per rule per document

Indexes: `(rule_id)`, `(status)`, `(es_index, es_document_id)`, `(created_at DESC)`

---

## Schema: `review`

### `review.queues`

| Column | Type | Constraints |
|---|---|---|
| `id` | uuid | PK, default `gen_random_uuid()` |
| `name` | text | NOT NULL |
| `description` | text | |
| `policy_id` | uuid | NOT NULL, FK → `policy.policies.id` ON DELETE RESTRICT |
| `created_by` | uuid | FK → `iam.users.id` |
| `created_at` | timestamptz | NOT NULL DEFAULT now() |
| `updated_at` | timestamptz | NOT NULL DEFAULT now() |

### `review.queue_batches`

A queue is divided into batches; each batch is assigned to one reviewer.

| Column | Type | Constraints |
|---|---|---|
| `id` | uuid | PK, default `gen_random_uuid()` |
| `queue_id` | uuid | NOT NULL, FK → `review.queues.id` ON DELETE CASCADE |
| `name` | text | e.g. `Batch 1`, `Alice batch` |
| `assigned_to` | uuid | FK → `iam.users.id` ON DELETE SET NULL |
| `assigned_by` | uuid | FK → `iam.users.id` ON DELETE SET NULL |
| `assigned_at` | timestamptz | |
| `status` | text | NOT NULL DEFAULT `pending`, CHECK IN (`pending`, `in_progress`, `completed`) |
| `created_at` | timestamptz | NOT NULL DEFAULT now() |
| `updated_at` | timestamptz | NOT NULL DEFAULT now() |

Indexes: `(queue_id)`, `(assigned_to)`

### `review.queue_items`

Individual alerts within a batch, ordered by `position`.

| Column | Type | Constraints |
|---|---|---|
| `id` | uuid | PK, default `gen_random_uuid()` |
| `batch_id` | uuid | NOT NULL, FK → `review.queue_batches.id` ON DELETE CASCADE |
| `alert_id` | uuid | NOT NULL, FK → `alert.alerts.id` ON DELETE RESTRICT |
| `position` | int | NOT NULL — display order within batch |
| `created_at` | timestamptz | NOT NULL DEFAULT now() |

Unique: `(batch_id, alert_id)`, `(batch_id, position)`

Indexes: `(batch_id)`, `(alert_id)`

### `review.decision_statuses`

Configuration table, maintained by admins.

| Column | Type | Constraints |
|---|---|---|
| `id` | uuid | PK, default `gen_random_uuid()` |
| `name` | text | UNIQUE NOT NULL |
| `description` | text | |
| `is_terminal` | boolean | NOT NULL DEFAULT false — if true, closes the alert |
| `display_order` | int | NOT NULL DEFAULT 0 |
| `created_at` | timestamptz | NOT NULL DEFAULT now() |

Seeded values:

| name | is_terminal | display_order |
|---|---|---|
| `acknowledged` | true | 10 |
| `false_positive` | true | 20 |
| `breach` | true | 30 |
| `escalated` | false | 40 |
| `pending_info` | false | 50 |

### `review.decisions`

One row per decision event; multiple decisions per alert are allowed.

| Column | Type | Constraints |
|---|---|---|
| `id` | uuid | PK, default `gen_random_uuid()` |
| `alert_id` | uuid | NOT NULL, FK → `alert.alerts.id` ON DELETE RESTRICT |
| `reviewer_id` | uuid | NOT NULL, FK → `iam.users.id` ON DELETE RESTRICT |
| `status_id` | uuid | NOT NULL, FK → `review.decision_statuses.id` ON DELETE RESTRICT |
| `comment` | text | |
| `decided_at` | timestamptz | NOT NULL DEFAULT now() |

Indexes: `(alert_id)`, `(reviewer_id)`

### `review.audit_log`

Append-only. UPDATE and DELETE are blocked by triggers.

| Column | Type | Constraints |
|---|---|---|
| `id` | uuid | PK, default `gen_random_uuid()` |
| `decision_id` | uuid | NOT NULL, FK → `review.decisions.id` ON DELETE CASCADE |
| `actor_id` | uuid | FK → `iam.users.id` |
| `action` | text | NOT NULL, CHECK IN (`created`, `updated`, `deleted`) |
| `old_values` | jsonb | Snapshot before change (NULL for creates) |
| `new_values` | jsonb | Snapshot after change (NULL for deletes) |
| `occurred_at` | timestamptz | NOT NULL DEFAULT now() |
| `ip_address` | inet | |
| `user_agent` | text | |

Indexes: `(decision_id)`, `(actor_id)`, `(occurred_at DESC)`

---

## Database Roles

| Role | Schema access |
|---|---|
| `iam_rw` | Read/write `iam`; read `—` |
| `policy_rw` | Read/write `policy`; read `iam` |
| `alert_rw` | Read/write `alert`; read `iam`, `policy` |
| `review_rw` | Read/write `review`; read `iam`, `policy`, `alert` |

Connection strings are injected via the `postgresql-credentials` Secret as `IAM_DATABASE_URL`, `POLICY_DATABASE_URL`, `ALERT_DATABASE_URL`, `REVIEW_DATABASE_URL`.

---

## Cross-Schema FK Summary

| FK column | References |
|---|---|
| `iam.user_groups.user_id` | `iam.users.id` |
| `iam.user_groups.group_id` | `iam.groups.id` |
| `iam.group_roles.group_id` | `iam.groups.id` |
| `iam.group_roles.role_id` | `iam.roles.id` |
| `policy.risk_models.created_by` | `iam.users.id` |
| `policy.policies.risk_model_id` | `policy.risk_models.id` |
| `policy.policies.created_by` | `iam.users.id` |
| `policy.rules.policy_id` | `policy.policies.id` |
| `policy.rules.created_by` | `iam.users.id` |
| `policy.group_policies.group_id` | `iam.groups.id` |
| `policy.group_policies.policy_id` | `policy.policies.id` |
| `alert.alerts.rule_id` | `policy.rules.id` |
| `review.queues.policy_id` | `policy.policies.id` |
| `review.queue_batches.queue_id` | `review.queues.id` |
| `review.queue_batches.assigned_to` | `iam.users.id` |
| `review.queue_items.batch_id` | `review.queue_batches.id` |
| `review.queue_items.alert_id` | `alert.alerts.id` |
| `review.decisions.alert_id` | `alert.alerts.id` |
| `review.decisions.reviewer_id` | `iam.users.id` |
| `review.decisions.status_id` | `review.decision_statuses.id` |
| `review.audit_log.decision_id` | `review.decisions.id` |
| `review.audit_log.actor_id` | `iam.users.id` |
