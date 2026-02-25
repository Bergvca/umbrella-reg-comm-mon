# PostgreSQL Schema Reference

Database: `umbrella`

Six schemas by domain:

| Schema | Purpose |
|---|---|
| `iam` | Users, groups, roles, RBAC |
| `policy` | Risk models, policies, KQL rules |
| `alert` | Alerts linked to Elasticsearch events |
| `review` | Decisions, statuses, review queues, audit trail |
| `entity` | Entity resolution — people, organizations, handles, attributes |
| `agent` | AI agent definitions, models, tools, runs, audit trail |

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

## Schema: `entity`

### `entity.entities`

| Column | Type | Constraints |
|---|---|---|
| `id` | uuid | PK, default `gen_random_uuid()` |
| `display_name` | text | NOT NULL |
| `entity_type` | text | NOT NULL — `'person'`, `'organization'`, `'distribution_list'` |
| `created_at` | timestamptz | NOT NULL DEFAULT now() |
| `updated_at` | timestamptz | NOT NULL DEFAULT now() |
| `created_by` | uuid | FK → `iam.users.id` |

Unique: `(display_name, entity_type)` · Indexes: `(entity_type)`

### `entity.handles`

Maps channel-specific identifiers to entities.

| Column | Type | Constraints |
|---|---|---|
| `id` | uuid | PK, default `gen_random_uuid()` |
| `entity_id` | uuid | NOT NULL, FK → `entity.entities.id` ON DELETE CASCADE |
| `handle_type` | text | NOT NULL — `'email'`, `'teams_id'`, `'bloomberg_uuid'`, `'turret_extension'` |
| `handle_value` | text | NOT NULL — normalized (lowercased for email) |
| `is_primary` | boolean | NOT NULL DEFAULT false |
| `created_at` | timestamptz | NOT NULL DEFAULT now() |

Unique: `(handle_type, handle_value)` — one handle maps to exactly one entity

Indexes: `(entity_id)`

### `entity.attributes`

Extensible key-value pairs with optional temporal validity.

| Column | Type | Constraints |
|---|---|---|
| `id` | uuid | PK, default `gen_random_uuid()` |
| `entity_id` | uuid | NOT NULL, FK → `entity.entities.id` ON DELETE CASCADE |
| `attr_key` | text | NOT NULL — e.g. `'company'`, `'department'`, `'title'` |
| `attr_value` | text | NOT NULL |
| `valid_from` | timestamptz | optional temporal validity |
| `valid_to` | timestamptz | optional temporal validity |
| `created_at` | timestamptz | NOT NULL DEFAULT now() |

Unique: `(entity_id, attr_key, valid_from)` — one value per key per time period

Indexes: `(entity_id)`

---

## Schema: `agent`

### `agent.models`

Registered LLM endpoints. Admins configure these; agent builders select from them.

| Column | Type | Constraints |
|---|---|---|
| `id` | uuid | PK, default `gen_random_uuid()` |
| `name` | text | UNIQUE NOT NULL |
| `provider` | text | NOT NULL — LiteLLM provider key, e.g. `openai`, `anthropic`, `ollama` |
| `model_id` | text | NOT NULL — provider-specific model ID |
| `base_url` | text | NULL for cloud providers; endpoint URL for self-hosted |
| `api_key_secret` | text | NULL — reference to K8s secret key |
| `max_tokens` | int | NOT NULL DEFAULT 4096 |
| `is_active` | boolean | NOT NULL DEFAULT true |
| `created_by` | uuid | FK → `iam.users.id` |
| `created_at` | timestamptz | NOT NULL DEFAULT now() |
| `updated_at` | timestamptz | NOT NULL DEFAULT now() |

### `agent.tools`

Registry of available tools (built-in and custom).

| Column | Type | Constraints |
|---|---|---|
| `id` | uuid | PK, default `gen_random_uuid()` |
| `name` | text | UNIQUE NOT NULL — machine name, e.g. `es_search`, `sql_query` |
| `display_name` | text | NOT NULL |
| `description` | text | NOT NULL — shown to the LLM as the tool description |
| `category` | text | NOT NULL, CHECK IN (`builtin`, `custom`) |
| `parameters_schema` | jsonb | NOT NULL — JSON Schema defining tool input |
| `is_active` | boolean | NOT NULL DEFAULT true |
| `created_at` | timestamptz | NOT NULL DEFAULT now() |

### `agent.agents`

Core agent definitions.

| Column | Type | Constraints |
|---|---|---|
| `id` | uuid | PK, default `gen_random_uuid()` |
| `name` | text | NOT NULL |
| `description` | text | |
| `model_id` | uuid | NOT NULL, FK → `agent.models.id` ON DELETE RESTRICT |
| `system_prompt` | text | NOT NULL |
| `temperature` | numeric(3,2) | NOT NULL DEFAULT 0.0 |
| `max_iterations` | int | NOT NULL DEFAULT 10 |
| `output_schema` | jsonb | NULL — if set, enforces structured output |
| `is_builtin` | boolean | NOT NULL DEFAULT false |
| `is_active` | boolean | NOT NULL DEFAULT true |
| `created_by` | uuid | FK → `iam.users.id` |
| `created_at` | timestamptz | NOT NULL DEFAULT now() |
| `updated_at` | timestamptz | NOT NULL DEFAULT now() |

Unique: `(name, created_by)` · Indexes: `(model_id)`, `(created_by)`

### `agent.agent_tools`

Many-to-many: which tools an agent can use.

| Column | Type | Constraints |
|---|---|---|
| `agent_id` | uuid | PK, FK → `agent.agents.id` ON DELETE CASCADE |
| `tool_id` | uuid | PK, FK → `agent.tools.id` ON DELETE CASCADE |
| `tool_config` | jsonb | NULL — per-agent tool overrides |

Indexes: `(tool_id)`

### `agent.agent_data_sources`

Per-agent data access control (ES indices and PG schemas).

| Column | Type | Constraints |
|---|---|---|
| `id` | uuid | PK, default `gen_random_uuid()` |
| `agent_id` | uuid | NOT NULL, FK → `agent.agents.id` ON DELETE CASCADE |
| `source_type` | text | NOT NULL, CHECK IN (`elasticsearch`, `postgresql`) |
| `source_identifier` | text | NOT NULL — ES index pattern or PG schema |
| `access_mode` | text | NOT NULL DEFAULT `read`, CHECK IN (`read`) |

Unique: `(agent_id, source_type, source_identifier)` · Indexes: `(agent_id)`

### `agent.runs`

Execution log for every agent invocation.

| Column | Type | Constraints |
|---|---|---|
| `id` | uuid | PK, default `gen_random_uuid()` |
| `agent_id` | uuid | NOT NULL, FK → `agent.agents.id` ON DELETE RESTRICT |
| `status` | text | NOT NULL DEFAULT `pending`, CHECK IN (`pending`, `running`, `completed`, `failed`, `cancelled`) |
| `input` | jsonb | NOT NULL |
| `output` | jsonb | NULL |
| `error_message` | text | NULL |
| `token_usage` | jsonb | NULL — `{ prompt_tokens, completion_tokens, total_tokens }` |
| `iterations` | int | NULL |
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

## Database Roles

| Role | Schema access |
|---|---|
| `iam_rw` | Read/write `iam`; read `—` |
| `policy_rw` | Read/write `policy`; read `iam` |
| `alert_rw` | Read/write `alert`; read `iam`, `policy` |
| `review_rw` | Read/write `review`; read `iam`, `policy`, `alert` |
| `entity_rw` | Read/write `entity`; read `iam` |
| `agent_rw` | Read/write `agent`; read `iam`, `entity` |
| `agent_readonly` | Read `agent`, `iam`, `entity`, `alert`, `review` |

Connection strings are injected via the `postgresql-credentials` Secret as `IAM_DATABASE_URL`, `POLICY_DATABASE_URL`, `ALERT_DATABASE_URL`, `REVIEW_DATABASE_URL`, `ENTITY_DATABASE_URL`, `AGENT_DATABASE_URL`.

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
| `entity.entities.created_by` | `iam.users.id` |
| `entity.handles.entity_id` | `entity.entities.id` |
| `entity.attributes.entity_id` | `entity.entities.id` |
| `agent.models.created_by` | `iam.users.id` |
| `agent.agents.model_id` | `agent.models.id` |
| `agent.agents.created_by` | `iam.users.id` |
| `agent.agent_tools.agent_id` | `agent.agents.id` |
| `agent.agent_tools.tool_id` | `agent.tools.id` |
| `agent.agent_data_sources.agent_id` | `agent.agents.id` |
| `agent.runs.agent_id` | `agent.agents.id` |
| `agent.runs.triggered_by` | `iam.users.id` |
| `agent.run_steps.run_id` | `agent.runs.id` |
