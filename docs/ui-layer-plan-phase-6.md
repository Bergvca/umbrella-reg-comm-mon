# Phase 6 — Message Search + Remaining Views (Detailed Plan)

## 1. Overview

Phase 6 completes all remaining frontend views, replacing the four `<ComingSoon>` placeholders in `App.tsx` with fully functional pages. It also enhances the queue detail page with supervisor batch management (create, assign, populate). All backend endpoints are already implemented — this phase is **pure frontend work**.

**Goal:** Every route in the sidebar is functional. Reviewers can search messages ad hoc, supervisors can manage queues and export data, admins can manage users/groups/policies/rules, and supervisors can view the audit trail.

**Scope:**

| Route | Page | Role | What it does |
|---|---|---|---|
| `/messages` | MessagesPage | reviewer+ | Full-text search across ES `messages-*` with filters and highlights |
| `/messages/:index/:docId` | MessageDetailPage | reviewer+ | Full message: body, participants, attachments, audio, enrichments, linked alerts |
| `/policies` | PoliciesPage | reviewer+ (read) / admin (write) | Risk model → policy → rule tree with CRUD for admins |
| `/admin` | AdminPage | admin | User CRUD, group management, role assignment, decision status config |
| `/audit` | AuditPage | supervisor+ | Filterable, paginated audit trail |
| `/queues/:id` | QueueDetailPage (enhanced) | supervisor+ | Batch creation, assignment, and item management |

**Dependencies:** All backend endpoints used by this phase are already implemented:
- `GET /api/v1/messages/search` — full-text search with filters and highlights
- `GET /api/v1/messages/{index}/{doc_id}` — single message from ES
- `GET /api/v1/messages/{index}/{doc_id}/audio` — pre-signed S3 URL
- `GET /api/v1/policies` — paginated policy list (filterable by risk_model_id, is_active)
- `POST /api/v1/policies` — create policy (admin)
- `GET /api/v1/policies/{id}` — policy detail (with risk_model_name, rule_count, group_count)
- `PATCH /api/v1/policies/{id}` — update policy (admin)
- `GET /api/v1/policies/{id}/rules` — rules for a policy
- `POST /api/v1/policies/{id}/rules` — create rule (admin)
- `PATCH /api/v1/rules/{id}` — update rule (admin)
- `DELETE /api/v1/rules/{id}` — soft-delete rule (admin)
- `GET /api/v1/policies/{id}/groups` — group-policy assignments
- `POST /api/v1/policies/{id}/groups` — assign group to policy (admin)
- `DELETE /api/v1/policies/{id}/groups/{group_id}` — remove group from policy (admin)
- `GET /api/v1/risk-models` — paginated risk models
- `POST /api/v1/risk-models` — create risk model (admin)
- `GET /api/v1/risk-models/{id}` — risk model detail (with policy_count)
- `PATCH /api/v1/risk-models/{id}` — update risk model (admin)
- `GET /api/v1/users` — paginated user list (admin)
- `POST /api/v1/users` — create user (admin)
- `GET /api/v1/users/{id}` — user with resolved roles (admin)
- `PATCH /api/v1/users/{id}` — update user (admin)
- `GET /api/v1/users/{id}/groups` — user's group memberships (admin)
- `POST /api/v1/users/{id}/groups` — add user to group (admin)
- `DELETE /api/v1/users/{id}/groups/{group_id}` — remove from group (admin)
- `GET /api/v1/groups` — paginated groups with roles and member_count (admin)
- `POST /api/v1/groups` — create group (admin)
- `GET /api/v1/groups/{id}` — group detail (admin)
- `PATCH /api/v1/groups/{id}` — update group (admin)
- `GET /api/v1/groups/{id}/members` — group members (admin)
- `POST /api/v1/groups/{id}/roles` — assign role to group (admin)
- `DELETE /api/v1/groups/{id}/roles/{role_id}` — remove role from group (admin)
- `GET /api/v1/roles` — all roles
- `GET /api/v1/decision-statuses` — decision status list (already wired from Phase 5)
- `GET /api/v1/audit-log` — paginated audit log (supervisor, filters: actor_id, alert_id, date_from, date_to)
- `GET /api/v1/export/alerts` — CSV/JSON alert export (supervisor)
- `GET /api/v1/export/messages` — CSV/JSON message export (supervisor)
- `POST /api/v1/queues/{id}/batches` — create batch (supervisor)
- `PATCH /api/v1/queues/{id}/batches/{bid}` — assign batch / update status (supervisor)
- `POST /api/v1/queues/{id}/batches/{bid}/items` — add item to batch (supervisor)

---

## 2. New shadcn/ui Components to Install

These components from `shadcn/ui` are needed and are **not yet installed** (existing: button, card, input, label, separator, avatar, badge, dropdown-menu, dialog, tooltip, select, table, pagination, textarea, tabs, skeleton, popover, calendar, command, scroll-area).

| Component | Used By | Purpose |
|---|---|---|
| **switch** | PolicyEditor, UserForm | Toggle active/inactive on policies, rules, users |
| **sheet** | MessageDetailPage, AdminPage | Slide-over panel for detail views without navigating away |
| **accordion** | PoliciesPage | Collapsible risk model → policy → rule tree |
| **alert-dialog** | RuleEditor, UserForm | Confirmation dialog for destructive actions (deactivate rule, deactivate user) |
| **form** | RuleEditor, UserForm, GroupForm | shadcn form components (wraps React Hook Form) |
| **toast** / **sonner** | All CRUD forms | Success/error notifications after mutations |
| **breadcrumb** | MessageDetailPage, PolicyEditor | Navigation breadcrumbs for nested views |

Install command:
```bash
cd ui/frontend
npx shadcn@latest add switch sheet accordion alert-dialog form sonner breadcrumb
```

---

## 3. New Types to Add

Add to `src/lib/types.ts`:

```typescript
// ── Message Search ─────────────────────────────────────

export interface ESMessageHit {
  message: ESMessage;
  index: string;
  score: number | null;
  highlights: Record<string, string[]>;
}

export interface MessageSearchResponse {
  hits: ESMessageHit[];
  total: number;
  offset: number;
  limit: number;
}

// ── Policy Detail ──────────────────────────────────────

export interface PolicyDetail extends PolicyOut {
  risk_model_name: string;
  rule_count: number;
  group_count: number;
}

export interface RiskModelDetail extends RiskModelOut {
  policy_count: number;
}

export interface GroupPolicyOut {
  group_id: string;
  policy_id: string;
  assigned_by: string | null;
  assigned_at: string;
}

// ── Group Detail ───────────────────────────────────────

export interface GroupDetail extends GroupOut {
  roles: string[];
  member_count: number;
}

// ── User with Roles ────────────────────────────────────

export interface UserWithRoles extends UserOut {
  roles: string[];
}

// ── Audit (extend existing) ────────────────────────────
// Update existing AuditLogEntry to match backend:

export interface AuditLogEntry {
  id: string;
  decision_id: string;
  actor_id: string | null;
  action: string;
  old_values: Record<string, unknown> | null;
  new_values: Record<string, unknown> | null;
  occurred_at: string;    // was: created_at
  ip_address: string | null;
  user_agent: string | null;
}
```

---

## 4. New Files to Create

### 4.1 API Modules (`src/api/`)

| File | Functions | Backend Endpoint |
|---|---|---|
| `src/api/messages.ts` (extend) | `searchMessages(params)`, `getMessage(index, docId)` | `GET /messages/search`, `GET /messages/{index}/{doc_id}` |
| `src/api/policies.ts` (new) | `getPolicies(params)`, `getPolicy(id)`, `createPolicy(body)`, `updatePolicy(id, body)`, `getRules(policyId, params)`, `createRule(policyId, body)`, `updateRule(ruleId, body)`, `deleteRule(ruleId)`, `getGroupPolicies(policyId)`, `assignGroupPolicy(policyId, groupId)`, `removeGroupPolicy(policyId, groupId)` | `GET/POST /policies`, `GET/PATCH /policies/{id}`, `GET/POST /policies/{id}/rules`, `PATCH/DELETE /rules/{id}`, `GET/POST/DELETE /policies/{id}/groups` |
| `src/api/risk-models.ts` (new) | `getRiskModels(params)`, `getRiskModel(id)`, `createRiskModel(body)`, `updateRiskModel(id, body)` | `GET/POST /risk-models`, `GET/PATCH /risk-models/{id}` |
| `src/api/users.ts` (new) | `getUsers(params)`, `getUser(id)`, `createUser(body)`, `updateUser(id, body)`, `getUserGroups(userId)`, `addUserToGroup(userId, groupId)`, `removeUserFromGroup(userId, groupId)` | `GET/POST /users`, `GET/PATCH /users/{id}`, `GET/POST/DELETE /users/{id}/groups` |
| `src/api/groups.ts` (new) | `getGroups(params)`, `getGroup(id)`, `createGroup(body)`, `updateGroup(id, body)`, `getGroupMembers(groupId)`, `assignRoleToGroup(groupId, roleId)`, `removeRoleFromGroup(groupId, roleId)` | `GET/POST /groups`, `GET/PATCH /groups/{id}`, `GET /groups/{id}/members`, `POST/DELETE /groups/{id}/roles` |
| `src/api/roles.ts` (new) | `getRoles()` | `GET /roles` |
| `src/api/audit.ts` (new) | `getAuditLog(params)` | `GET /audit-log` |
| `src/api/export.ts` (new) | `exportAlerts(params)`, `exportMessages(params)` | `GET /export/alerts`, `GET /export/messages` |
| `src/api/queues.ts` (extend) | `createQueue(body)`, `createBatch(queueId, body)`, `updateBatch(queueId, batchId, body)`, `addItemToBatch(queueId, batchId, body)` | `POST /queues`, `POST/PATCH /queues/{id}/batches`, `POST /queues/{id}/batches/{bid}/items` |

### 4.2 TanStack Query Hooks (`src/hooks/`)

| File | Hooks | Query Keys |
|---|---|---|
| `src/hooks/useMessages.ts` (new) | `useMessageSearch(params)`, `useMessage(index, docId)` | `["messages", "search", params]`, `["messages", index, docId]` |
| `src/hooks/usePolicies.ts` (new) | `usePolicies(params)`, `usePolicy(id)`, `useCreatePolicy()`, `useUpdatePolicy()`, `useRules(policyId, params)`, `useCreateRule(policyId)`, `useUpdateRule()`, `useDeleteRule()`, `useGroupPolicies(policyId)`, `useAssignGroupPolicy(policyId)`, `useRemoveGroupPolicy(policyId)` | `["policies", ...]`, `["rules", policyId, ...]` |
| `src/hooks/useRiskModels.ts` (new) | `useRiskModels(params)`, `useRiskModel(id)`, `useCreateRiskModel()`, `useUpdateRiskModel()` | `["risk-models", ...]` |
| `src/hooks/useUsers.ts` (new) | `useUsers(params)`, `useUser(id)`, `useCreateUser()`, `useUpdateUser()`, `useUserGroups(userId)`, `useAddUserToGroup(userId)`, `useRemoveUserFromGroup(userId)` | `["users", ...]` |
| `src/hooks/useGroups.ts` (new) | `useGroups(params)`, `useGroup(id)`, `useCreateGroup()`, `useUpdateGroup()`, `useGroupMembers(groupId)`, `useAssignRoleToGroup(groupId)`, `useRemoveRoleFromGroup(groupId)` | `["groups", ...]` |
| `src/hooks/useRoles.ts` (new) | `useRoles()` | `["roles"]` |
| `src/hooks/useAuditLog.ts` (new) | `useAuditLog(params)` | `["audit-log", params]` |
| `src/hooks/useQueues.ts` (extend) | `useCreateQueue()`, `useCreateBatch(queueId)`, `useUpdateBatch(queueId)`, `useAddItemToBatch(queueId, batchId)` | Invalidates `["queues", ...]` |

### 4.3 Pages (`src/pages/`)

| File | Role | Description |
|---|---|---|
| `src/pages/MessagesPage.tsx` (new) | reviewer+ | Full-text search with filters, paginated results with highlights |
| `src/pages/MessageDetailPage.tsx` (new) | reviewer+ | Full message display + linked alerts |
| `src/pages/PoliciesPage.tsx` (new) | reviewer+ (read) / admin (CRUD) | Risk model → policy → rule tree |
| `src/pages/AdminPage.tsx` (new) | admin | Tabbed view: Users, Groups, Decision Statuses |
| `src/pages/AuditPage.tsx` (new) | supervisor+ | Filterable audit log table |

### 4.4 Components (`src/components/`)

| File | Props | Description |
|---|---|---|
| **messages/** | | |
| `MessageSearchForm.tsx` | `params, onChange, onSubmit` | Search bar + expandable filter panel |
| `MessageSearchResults.tsx` | `results: ESMessageHit[], onSelect` | Result list with highlighted snippets |
| `MessageHighlight.tsx` | `fragments: string[]` | Renders ES highlight HTML fragments safely |
| `LinkedAlerts.tsx` | `alerts: AlertOut[]` | List of alerts linked to a message (from message_id → alerts) |
| **policies/** | | |
| `RiskModelList.tsx` | `role-aware` | Accordion list of risk models, expandable to show policies |
| `RiskModelForm.tsx` | `riskModel?, onSuccess` | Dialog form for create/edit risk model |
| `PolicyList.tsx` | `riskModelId, onSelect` | Policy cards within a risk model accordion |
| `PolicyForm.tsx` | `policy?, riskModelId, onSuccess` | Dialog form for create/edit policy |
| `PolicyDetail.tsx` | `policyId` | Policy info + rules table + group assignments |
| `RuleTable.tsx` | `rules, policyId, isAdmin` | Table of rules with severity badge, active toggle, edit/delete |
| `RuleForm.tsx` | `rule?, policyId, onSuccess` | Dialog form for create/edit rule with KQL textarea |
| `GroupPolicyManager.tsx` | `policyId` | Assign/remove groups from a policy |
| **admin/** | | |
| `UserTable.tsx` | `users, total, offset, limit, onPageChange` | Paginated user list with actions |
| `UserForm.tsx` | `user?, onSuccess` | Dialog form for create/edit user |
| `UserGroupManager.tsx` | `userId` | Manage a user's group memberships |
| `GroupTable.tsx` | `groups, total, offset, limit, onPageChange` | Paginated group list with role/member counts |
| `GroupForm.tsx` | `group?, onSuccess` | Dialog form for create/edit group |
| `GroupDetailPanel.tsx` | `groupId` | Sheet panel showing group members + roles with management |
| `RoleAssignmentManager.tsx` | `groupId` | Add/remove roles from a group |
| `DecisionStatusTable.tsx` | — | Read-only table of decision statuses (display_order, is_terminal) |
| **audit/** | | |
| `AuditLogTable.tsx` | `entries, total, offset, limit, onPageChange` | Paginated table with action, actor, timestamp columns |
| `AuditFilterBar.tsx` | `filters, onChange` | Filters: actor, alert, date range |
| `AuditDetailDialog.tsx` | `entry: AuditLogEntry` | Dialog showing old_values / new_values JSON diff |
| **queues/** (enhancements) | | |
| `CreateQueueDialog.tsx` | `onSuccess` | Dialog: queue name, description, policy selection |
| `CreateBatchDialog.tsx` | `queueId, onSuccess` | Dialog: optional batch name |
| `BatchAssignDialog.tsx` | `queueId, batchId, onSuccess` | Dialog: select reviewer to assign batch to |
| `AddItemDialog.tsx` | `queueId, batchId, onSuccess` | Dialog: select alert to add to batch (with position) |
| `BatchTable.tsx` | `batches, queueId, isSupervisor` | Table of batches with status, assignment, actions |
| **export/** | | |
| `ExportButton.tsx` | `type: "alerts" \| "messages", params` | Dropdown button (CSV / JSON) that triggers download |

---

## 5. Detailed Implementation Steps

### Step 1 — Install shadcn/ui Components

```bash
cd ui/frontend
npx shadcn@latest add switch sheet accordion alert-dialog form sonner breadcrumb
```

Verify components land in `src/components/ui/`.

Add `<Toaster />` from `sonner` to `main.tsx` (or `App.tsx`) for toast notifications:

```tsx
import { Toaster } from "@/components/ui/sonner";

// in root component:
<QueryClientProvider client={queryClient}>
  <BrowserRouter>
    <App />
    <Toaster />
  </BrowserRouter>
</QueryClientProvider>
```

---

### Step 2 — Add Types to `lib/types.ts`

Add the types listed in Section 3 above: `ESMessageHit`, `MessageSearchResponse`, `PolicyDetail`, `RiskModelDetail`, `GroupPolicyOut`, `GroupDetail`, `UserWithRoles`. Update `AuditLogEntry` to match the actual backend schema (field names: `occurred_at`, `ip_address`, `user_agent`).

---

### Step 3 — API Modules

#### 3a. Extend `src/api/messages.ts`

Add message search and single-message retrieval alongside the existing `getAudioUrl`:

```typescript
import { apiFetch } from "./client";
import type { ESMessage, MessageSearchResponse } from "@/lib/types";

export interface MessageSearchParams {
  q?: string;
  channel?: string;
  direction?: string;
  participant?: string;
  date_from?: string;
  date_to?: string;
  sentiment?: string;
  risk_score_min?: number;
  offset?: number;
  limit?: number;
}

export async function searchMessages(
  params: MessageSearchParams = {},
): Promise<MessageSearchResponse> {
  const sp = new URLSearchParams();
  if (params.q) sp.set("q", params.q);
  if (params.channel) sp.set("channel", params.channel);
  if (params.direction) sp.set("direction", params.direction);
  if (params.participant) sp.set("participant", params.participant);
  if (params.date_from) sp.set("date_from", params.date_from);
  if (params.date_to) sp.set("date_to", params.date_to);
  if (params.sentiment) sp.set("sentiment", params.sentiment);
  if (params.risk_score_min != null)
    sp.set("risk_score_min", String(params.risk_score_min));
  sp.set("offset", String(params.offset ?? 0));
  sp.set("limit", String(params.limit ?? 20));
  return apiFetch(`/messages/search?${sp.toString()}`);
}

export async function getMessage(
  index: string,
  docId: string,
): Promise<ESMessage> {
  return apiFetch(`/messages/${index}/${docId}`);
}

// ... existing getAudioUrl stays ...
```

#### 3b. Create `src/api/policies.ts`

```typescript
import { apiFetch } from "./client";
import type { PolicyDetail, PolicyOut, RuleOut, GroupPolicyOut, PaginatedResponse } from "@/lib/types";

export interface PolicyListParams {
  risk_model_id?: string;
  is_active?: boolean;
  offset?: number;
  limit?: number;
}

export async function getPolicies(params: PolicyListParams = {}): Promise<PaginatedResponse<PolicyDetail>> {
  const sp = new URLSearchParams();
  if (params.risk_model_id) sp.set("risk_model_id", params.risk_model_id);
  if (params.is_active !== undefined) sp.set("is_active", String(params.is_active));
  sp.set("offset", String(params.offset ?? 0));
  sp.set("limit", String(params.limit ?? 50));
  return apiFetch(`/policies?${sp.toString()}`);
}

export async function getPolicy(id: string): Promise<PolicyDetail> {
  return apiFetch(`/policies/${id}`);
}

export async function createPolicy(body: { risk_model_id: string; name: string; description?: string }): Promise<PolicyOut> {
  return apiFetch("/policies", { method: "POST", body: JSON.stringify(body) });
}

export async function updatePolicy(id: string, body: { name?: string; description?: string; is_active?: boolean }): Promise<PolicyOut> {
  return apiFetch(`/policies/${id}`, { method: "PATCH", body: JSON.stringify(body) });
}

export async function getRules(policyId: string, params: { offset?: number; limit?: number } = {}): Promise<PaginatedResponse<RuleOut>> {
  const sp = new URLSearchParams();
  sp.set("offset", String(params.offset ?? 0));
  sp.set("limit", String(params.limit ?? 50));
  return apiFetch(`/policies/${policyId}/rules?${sp.toString()}`);
}

export async function createRule(policyId: string, body: { name: string; description?: string; kql: string; severity: string }): Promise<RuleOut> {
  return apiFetch(`/policies/${policyId}/rules`, { method: "POST", body: JSON.stringify(body) });
}

export async function updateRule(ruleId: string, body: { name?: string; description?: string; kql?: string; severity?: string; is_active?: boolean }): Promise<RuleOut> {
  return apiFetch(`/rules/${ruleId}`, { method: "PATCH", body: JSON.stringify(body) });
}

export async function deleteRule(ruleId: string): Promise<void> {
  return apiFetch(`/rules/${ruleId}`, { method: "DELETE" });
}

export async function getGroupPolicies(policyId: string): Promise<GroupPolicyOut[]> {
  return apiFetch(`/policies/${policyId}/groups`);
}

export async function assignGroupPolicy(policyId: string, groupId: string): Promise<void> {
  return apiFetch(`/policies/${policyId}/groups`, { method: "POST", body: JSON.stringify({ group_id: groupId }) });
}

export async function removeGroupPolicy(policyId: string, groupId: string): Promise<void> {
  return apiFetch(`/policies/${policyId}/groups/${groupId}`, { method: "DELETE" });
}
```

#### 3c. Create `src/api/risk-models.ts`

```typescript
import { apiFetch } from "./client";
import type { RiskModelDetail, RiskModelOut, PaginatedResponse } from "@/lib/types";

export async function getRiskModels(params: { is_active?: boolean; offset?: number; limit?: number } = {}): Promise<PaginatedResponse<RiskModelDetail>> {
  const sp = new URLSearchParams();
  if (params.is_active !== undefined) sp.set("is_active", String(params.is_active));
  sp.set("offset", String(params.offset ?? 0));
  sp.set("limit", String(params.limit ?? 50));
  return apiFetch(`/risk-models?${sp.toString()}`);
}

export async function getRiskModel(id: string): Promise<RiskModelDetail> {
  return apiFetch(`/risk-models/${id}`);
}

export async function createRiskModel(body: { name: string; description?: string }): Promise<RiskModelOut> {
  return apiFetch("/risk-models", { method: "POST", body: JSON.stringify(body) });
}

export async function updateRiskModel(id: string, body: { name?: string; description?: string; is_active?: boolean }): Promise<RiskModelOut> {
  return apiFetch(`/risk-models/${id}`, { method: "PATCH", body: JSON.stringify(body) });
}
```

#### 3d. Create `src/api/users.ts`

```typescript
import { apiFetch } from "./client";
import type { UserOut, UserWithRoles, GroupOut, PaginatedResponse } from "@/lib/types";

export async function getUsers(params: { offset?: number; limit?: number } = {}): Promise<PaginatedResponse<UserOut>> {
  const sp = new URLSearchParams();
  sp.set("offset", String(params.offset ?? 0));
  sp.set("limit", String(params.limit ?? 50));
  return apiFetch(`/users?${sp.toString()}`);
}

export async function getUser(id: string): Promise<UserWithRoles> {
  return apiFetch(`/users/${id}`);
}

export async function createUser(body: { username: string; email: string; password: string }): Promise<UserOut> {
  return apiFetch("/users", { method: "POST", body: JSON.stringify(body) });
}

export async function updateUser(id: string, body: { email?: string; is_active?: boolean }): Promise<UserOut> {
  return apiFetch(`/users/${id}`, { method: "PATCH", body: JSON.stringify(body) });
}

export async function getUserGroups(userId: string): Promise<GroupOut[]> {
  return apiFetch(`/users/${userId}/groups`);
}

export async function addUserToGroup(userId: string, groupId: string): Promise<void> {
  return apiFetch(`/users/${userId}/groups`, { method: "POST", body: JSON.stringify({ group_id: groupId }) });
}

export async function removeUserFromGroup(userId: string, groupId: string): Promise<void> {
  return apiFetch(`/users/${userId}/groups/${groupId}`, { method: "DELETE" });
}
```

#### 3e. Create `src/api/groups.ts`

```typescript
import { apiFetch } from "./client";
import type { GroupOut, GroupDetail, UserOut, PaginatedResponse } from "@/lib/types";

export async function getGroups(params: { offset?: number; limit?: number } = {}): Promise<PaginatedResponse<GroupDetail>> {
  const sp = new URLSearchParams();
  sp.set("offset", String(params.offset ?? 0));
  sp.set("limit", String(params.limit ?? 50));
  return apiFetch(`/groups?${sp.toString()}`);
}

export async function getGroup(id: string): Promise<GroupDetail> {
  return apiFetch(`/groups/${id}`);
}

export async function createGroup(body: { name: string; description?: string }): Promise<GroupOut> {
  return apiFetch("/groups", { method: "POST", body: JSON.stringify(body) });
}

export async function updateGroup(id: string, body: { name?: string; description?: string }): Promise<GroupOut> {
  return apiFetch(`/groups/${id}`, { method: "PATCH", body: JSON.stringify(body) });
}

export async function getGroupMembers(groupId: string): Promise<UserOut[]> {
  return apiFetch(`/groups/${groupId}/members`);
}

export async function assignRoleToGroup(groupId: string, roleId: string): Promise<void> {
  return apiFetch(`/groups/${groupId}/roles`, { method: "POST", body: JSON.stringify({ role_id: roleId }) });
}

export async function removeRoleFromGroup(groupId: string, roleId: string): Promise<void> {
  return apiFetch(`/groups/${groupId}/roles/${roleId}`, { method: "DELETE" });
}
```

#### 3f. Create `src/api/roles.ts`

```typescript
import { apiFetch } from "./client";
import type { RoleOut } from "@/lib/types";

export async function getRoles(): Promise<RoleOut[]> {
  return apiFetch("/roles");
}
```

#### 3g. Create `src/api/audit.ts`

```typescript
import { apiFetch } from "./client";
import type { AuditLogEntry, PaginatedResponse } from "@/lib/types";

export interface AuditLogParams {
  actor_id?: string;
  alert_id?: string;
  date_from?: string;
  date_to?: string;
  offset?: number;
  limit?: number;
}

export async function getAuditLog(params: AuditLogParams = {}): Promise<PaginatedResponse<AuditLogEntry>> {
  const sp = new URLSearchParams();
  if (params.actor_id) sp.set("actor_id", params.actor_id);
  if (params.alert_id) sp.set("alert_id", params.alert_id);
  if (params.date_from) sp.set("date_from", params.date_from);
  if (params.date_to) sp.set("date_to", params.date_to);
  sp.set("offset", String(params.offset ?? 0));
  sp.set("limit", String(params.limit ?? 50));
  return apiFetch(`/audit-log?${sp.toString()}`);
}
```

#### 3h. Create `src/api/export.ts`

Export endpoints return file downloads (not JSON), so use `window.open` or raw `fetch`:

```typescript
const BASE_URL = "/api/v1";

export function buildExportUrl(
  type: "alerts" | "messages",
  params: Record<string, string>,
  format: "csv" | "json" = "csv",
): string {
  const sp = new URLSearchParams(params);
  sp.set("format", format);
  return `${BASE_URL}/export/${type}?${sp.toString()}`;
}
```

The `ExportButton` component will use this URL with the auth token to trigger a download.

#### 3i. Extend `src/api/queues.ts`

Add queue/batch management mutations to the existing file:

```typescript
export async function createQueue(body: { name: string; description?: string; policy_id: string }): Promise<QueueOut> {
  return apiFetch("/queues", { method: "POST", body: JSON.stringify(body) });
}

export async function createBatch(queueId: string, body: { name?: string }): Promise<BatchOut> {
  return apiFetch(`/queues/${queueId}/batches`, { method: "POST", body: JSON.stringify(body) });
}

export async function updateBatch(queueId: string, batchId: string, body: { assigned_to?: string } | { status?: string }): Promise<BatchOut> {
  return apiFetch(`/queues/${queueId}/batches/${batchId}`, { method: "PATCH", body: JSON.stringify(body) });
}

export async function addItemToBatch(queueId: string, batchId: string, body: { alert_id: string; position: number }): Promise<QueueItemOut> {
  return apiFetch(`/queues/${queueId}/batches/${batchId}/items`, { method: "POST", body: JSON.stringify(body) });
}
```

---

### Step 4 — TanStack Query Hooks

#### 4a. Create `src/hooks/useMessages.ts`

```typescript
import { useQuery } from "@tanstack/react-query";
import { searchMessages, getMessage } from "@/api/messages";
import type { MessageSearchParams } from "@/api/messages";

export function useMessageSearch(params: MessageSearchParams) {
  return useQuery({
    queryKey: ["messages", "search", params],
    queryFn: () => searchMessages(params),
    enabled: !!(params.q || params.channel || params.participant || params.date_from),
    // Only search when at least one filter is provided
  });
}

export function useMessage(index: string, docId: string) {
  return useQuery({
    queryKey: ["messages", index, docId],
    queryFn: () => getMessage(index, docId),
    enabled: !!index && !!docId,
  });
}
```

#### 4b. Create `src/hooks/usePolicies.ts`

```typescript
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import * as policiesApi from "@/api/policies";

export function usePolicies(params: policiesApi.PolicyListParams = {}) {
  return useQuery({
    queryKey: ["policies", "list", params],
    queryFn: () => policiesApi.getPolicies(params),
  });
}

export function usePolicy(id: string) {
  return useQuery({
    queryKey: ["policies", id],
    queryFn: () => policiesApi.getPolicy(id),
    enabled: !!id,
  });
}

export function useCreatePolicy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: policiesApi.createPolicy,
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ["policies"] }); },
  });
}

export function useUpdatePolicy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: { id: string; name?: string; description?: string; is_active?: boolean }) =>
      policiesApi.updatePolicy(id, body),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ["policies"] }); },
  });
}

export function useRules(policyId: string, params: { offset?: number; limit?: number } = {}) {
  return useQuery({
    queryKey: ["rules", policyId, params],
    queryFn: () => policiesApi.getRules(policyId, params),
    enabled: !!policyId,
  });
}

export function useCreateRule(policyId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string; description?: string; kql: string; severity: string }) =>
      policiesApi.createRule(policyId, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["rules", policyId] });
      void qc.invalidateQueries({ queryKey: ["policies"] }); // rule_count changed
    },
  });
}

export function useUpdateRule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ ruleId, ...body }: { ruleId: string; name?: string; description?: string; kql?: string; severity?: string; is_active?: boolean }) =>
      policiesApi.updateRule(ruleId, body),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ["rules"] }); },
  });
}

export function useDeleteRule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: policiesApi.deleteRule,
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ["rules"] }); },
  });
}

export function useGroupPolicies(policyId: string) {
  return useQuery({
    queryKey: ["policies", policyId, "groups"],
    queryFn: () => policiesApi.getGroupPolicies(policyId),
    enabled: !!policyId,
  });
}

export function useAssignGroupPolicy(policyId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (groupId: string) => policiesApi.assignGroupPolicy(policyId, groupId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["policies", policyId, "groups"] });
      void qc.invalidateQueries({ queryKey: ["policies"] }); // group_count changed
    },
  });
}

export function useRemoveGroupPolicy(policyId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (groupId: string) => policiesApi.removeGroupPolicy(policyId, groupId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["policies", policyId, "groups"] });
      void qc.invalidateQueries({ queryKey: ["policies"] });
    },
  });
}
```

#### 4c. Create `src/hooks/useRiskModels.ts`

```typescript
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import * as api from "@/api/risk-models";

export function useRiskModels(params: { is_active?: boolean; offset?: number; limit?: number } = {}) {
  return useQuery({
    queryKey: ["risk-models", "list", params],
    queryFn: () => api.getRiskModels(params),
  });
}

export function useRiskModel(id: string) {
  return useQuery({
    queryKey: ["risk-models", id],
    queryFn: () => api.getRiskModel(id),
    enabled: !!id,
  });
}

export function useCreateRiskModel() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.createRiskModel,
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ["risk-models"] }); },
  });
}

export function useUpdateRiskModel() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: { id: string; name?: string; description?: string; is_active?: boolean }) =>
      api.updateRiskModel(id, body),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ["risk-models"] }); },
  });
}
```

#### 4d–4g. Create `useUsers.ts`, `useGroups.ts`, `useRoles.ts`, `useAuditLog.ts`

Follow the same patterns as above. Each mutation hook invalidates the relevant query keys. `useRoles()` is a simple query with `staleTime: 10 * 60 * 1000` (roles rarely change).

#### 4h. Extend `src/hooks/useQueues.ts`

Add mutation hooks for queue/batch management:

```typescript
export function useCreateQueue() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createQueue,
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ["queues"] }); },
  });
}

export function useCreateBatch(queueId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { name?: string }) => createBatch(queueId, body),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ["queues", queueId] }); },
  });
}

export function useUpdateBatch(queueId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ batchId, ...body }: { batchId: string; assigned_to?: string } | { batchId: string; status?: string }) =>
      updateBatch(queueId, batchId, body),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ["queues", queueId] }); },
  });
}

export function useAddItemToBatch(queueId: string, batchId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { alert_id: string; position: number }) =>
      addItemToBatch(queueId, batchId, body),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ["batches", batchId, "items"] }); },
  });
}
```

---

### Step 5 — Messages Page (`/messages`)

#### 5a. `MessageSearchForm` (`src/components/messages/MessageSearchForm.tsx`)

The primary search interface. A search bar with an expandable filter panel below.

```
Props: {
  params: MessageSearchParams;
  onChange: (params: MessageSearchParams) => void;
  onSubmit: () => void;
  isLoading: boolean;
}

Layout:
┌──────────────────────────────────────────────────────────────────────┐
│  [🔍 Search messages...                                   ] [Search] │
│                                                                      │
│  ▾ Filters                                                           │
│  Channel: [All ▾]   Direction: [All ▾]   Participant: [________]     │
│  Date from: [______]   Date to: [______]                             │
│  Sentiment: [All ▾]   Min risk score: [______]                       │
│                                                         [Clear all]  │
└──────────────────────────────────────────────────────────────────────┘

Components used:
- <Input> for query text
- <Button> for submit
- <Select> for channel (options from CHANNELS constant), direction, sentiment
- <Input type="number"> for risk_score_min
- <Popover> + <Calendar> for date range (reuse pattern from AlertFilters)
- <Input> for participant (free text — searches participant.name + id)
- Collapsible filter section via a simple toggle state
```

Search params are synced to URL `searchParams` so searches are bookmarkable. Submit triggers on Enter in the search bar or click of the Search button.

#### 5b. `MessageSearchResults` (`src/components/messages/MessageSearchResults.tsx`)

```
Props: {
  results: ESMessageHit[];
  total: number;
  offset: number;
  limit: number;
  onPageChange: (offset: number) => void;
  onSelect: (index: string, docId: string) => void;
}

Layout:
┌──────────────────────────────────────────────────────────────────────┐
│  Showing {offset+1}–{offset+results.length} of {total} results      │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │ 📧 email  •  2024-03-15 10:30                 Score: 8.2      │  │
│  │ From: John Doe → To: Jane Smith                               │  │
│  │ ...highlighted <em>matching</em> text snippet...              │  │
│  └────────────────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │ 💬 teams_chat  •  2024-03-14 16:45             Score: 6.5     │  │
│  │ ...                                                           │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  <Pagination>                                                        │
└──────────────────────────────────────────────────────────────────────┘

Each result card shows:
- Channel icon + badge
- Timestamp (formatted)
- Relevance score (if available)
- First 2 participants (from → to)
- Highlighted snippet from body_text, transcript, or translated_text
- Click card → navigate to /messages/{index}/{docId}

Empty state: "No messages match your search."
```

#### 5c. `MessageHighlight` (`src/components/messages/MessageHighlight.tsx`)

Renders ES highlight fragments. The backend returns HTML with `<em>` tags for highlights.

```
Props: { fragments: string[] }

Renders: Join fragments with "..." separator. Use dangerouslySetInnerHTML but
ONLY for <em> tags — strip all other HTML to prevent XSS. Use a sanitization
function that whitelists only <em> tags.
```

#### 5d. `MessagesPage` (`src/pages/MessagesPage.tsx`)

Orchestrates search form, results, and data fetching.

```
State:
- searchParams synced to URL (q, channel, direction, participant, date_from, date_to, sentiment, risk_score_min, offset)

Data:
- useMessageSearch(params) — only fires when at least one filter is set

Layout:
┌──────────────────────────────────────────────────────────────────────┐
│  <h1>Message Search</h1>                                             │
│                                                                      │
│  <MessageSearchForm params={params} onChange={setParams}             │
│    onSubmit={handleSubmit} isLoading={isLoading} />                  │
│                                                                      │
│  {/* Show results only after a search is performed */}               │
│  {hasSearched && (                                                   │
│    <MessageSearchResults results={data.hits} total={data.total}      │
│      offset={data.offset} limit={data.limit}                        │
│      onPageChange={setOffset}                                        │
│      onSelect={(index, docId) => navigate(`/messages/${index}/${docId}`)} />
│  )}                                                                  │
│                                                                      │
│  {/* Export button (supervisor+) */}                                 │
│  {hasRole(roles, "supervisor") && hasSearched && (                   │
│    <ExportButton type="messages" params={currentSearchParams} />     │
│  )}                                                                  │
└──────────────────────────────────────────────────────────────────────┘
```

---

### Step 6 — Message Detail Page (`/messages/:index/:docId`)

#### 6a. `MessageDetailPage` (`src/pages/MessageDetailPage.tsx`)

A dedicated page for viewing a single message, reusing the existing `MessageDisplay` component from Phase 5 and adding a linked-alerts section.

```
Route params: { index, docId } from useParams()

Data:
- useMessage(index, docId) — fetches full ES document
- (stretch) Query alerts where es_document_id = docId to show linked alerts

Layout:
┌──────────────────────────────────────────────────────────────────────┐
│  <Breadcrumb>                                                        │
│    Messages > {message.channel} > {message.message_id}               │
│  </Breadcrumb>                                                       │
│                                                                      │
│  <MessageDisplay message={message} esIndex={index} />                │
│  {/* Reuses the full Phase 5 component: body, participants,          │
│      attachments, audio player, enrichments */}                      │
│                                                                      │
│  ── Linked Alerts ──                                                 │
│  <LinkedAlerts alerts={linkedAlerts} />                              │
│  {/* Shows alerts that reference this message via es_document_id */} │
└──────────────────────────────────────────────────────────────────────┘

Loading: Full-page skeleton
Error: "Message not found" with back link
```

#### 6b. `LinkedAlerts` (`src/components/messages/LinkedAlerts.tsx`)

```
Props: { alerts: AlertOut[] }

Renders a compact list of alerts linked to this message.
Each item: severity badge + alert name + status badge, links to /alerts/{id}.
Empty state: "No alerts linked to this message."
```

Note: The backend's `GET /alerts` endpoint supports filtering by `es_document_id` implicitly through the alert model. If a direct filter is not available, this section can be deferred or implemented via a client-side match. Alternatively, the alert list can be shown as "Related alerts" using a search by the message_id.

---

### Step 7 — Policies Page (`/policies`)

The policies page uses an accordion-based tree view: Risk Models → Policies → Rules.

#### 7a. `RiskModelList` (`src/components/policies/RiskModelList.tsx`)

```
Data:
- useRiskModels()
- Role-awareness: admins see Create button + edit controls

Layout:
┌──────────────────────────────────────────────────────────────────────┐
│  Risk Models                              {isAdmin && [+ New Model]} │
│                                                                      │
│  <Accordion type="multiple">                                         │
│    {riskModels.map(rm => (                                           │
│      <AccordionItem key={rm.id}>                                     │
│        <AccordionTrigger>                                            │
│          {rm.name}                                                    │
│          <Badge>{rm.policy_count} policies</Badge>                   │
│          {!rm.is_active && <Badge variant="outline">Inactive</Badge>}│
│          {isAdmin && <EditButton />}                                 │
│        </AccordionTrigger>                                           │
│        <AccordionContent>                                            │
│          <PolicyList riskModelId={rm.id} />                          │
│        </AccordionContent>                                           │
│      </AccordionItem>                                                │
│    ))}                                                               │
│  </Accordion>                                                        │
└──────────────────────────────────────────────────────────────────────┘
```

#### 7b. `PolicyList` (`src/components/policies/PolicyList.tsx`)

```
Props: { riskModelId: string }

Data:
- usePolicies({ risk_model_id: riskModelId })

Layout:
  Grid of policy cards. Each card shows:
  - Policy name + active/inactive badge
  - Rule count, group count
  - Click → expand inline to show PolicyDetail, or navigate to /policies/{id}
  - Admin: "+ New Policy" button
```

#### 7c. `PolicyDetail` (`src/components/policies/PolicyDetail.tsx`)

```
Props: { policyId: string }

Data:
- usePolicy(policyId)
- useRules(policyId)
- useGroupPolicies(policyId)

Layout:
┌──────────────────────────────────────────────────────────────────────┐
│  Policy: {policy.name}           {isAdmin && [Edit] [Toggle Active]} │
│  Risk Model: {policy.risk_model_name}                                │
│  Description: {policy.description}                                   │
│                                                                      │
│  ── Rules ({rules.total}) ──                      {isAdmin && [+]}   │
│  <RuleTable rules={rules.items} policyId={policyId} />              │
│                                                                      │
│  ── Group Assignments ({groupPolicies.length}) ── {isAdmin && [+]}   │
│  <GroupPolicyManager policyId={policyId} />                          │
└──────────────────────────────────────────────────────────────────────┘
```

#### 7d. `RuleTable` (`src/components/policies/RuleTable.tsx`)

```
Props: { rules: RuleOut[], policyId: string, isAdmin: boolean }

Table columns:
| Name | KQL (truncated) | Severity (badge) | Active (switch) | Actions |

- Severity uses AlertSeverityBadge (reuse from Phase 5)
- Active toggle: <Switch> that calls useUpdateRule({ ruleId, is_active: !current })
- Actions (admin only): Edit button → opens RuleForm dialog, Delete → confirmation dialog
- Delete is a soft-delete (sets is_active = false via DELETE endpoint)
```

#### 7e. `RuleForm` (`src/components/policies/RuleForm.tsx`)

```
Props: { rule?: RuleOut; policyId: string; onSuccess: () => void }

A Dialog form for creating/editing rules.

Fields:
- Name: <Input>
- Description: <Textarea> (optional)
- KQL: <Textarea className="font-mono"> (monospace for KQL syntax)
- Severity: <Select> (critical, high, medium, low)

Uses React Hook Form + Zod for validation:
- name: required, min 1 char
- kql: required, min 1 char
- severity: required, must be one of the 4 levels

On submit:
- If rule prop exists → useUpdateRule()
- Else → useCreateRule(policyId)
- On success: close dialog, toast success, call onSuccess
```

#### 7f. `RiskModelForm`, `PolicyForm`

Similar dialog forms for creating/editing risk models and policies. Follow the same pattern as `RuleForm`.

#### 7g. `GroupPolicyManager` (`src/components/policies/GroupPolicyManager.tsx`)

```
Props: { policyId: string }

Data:
- useGroupPolicies(policyId)
- useGroups() — for the "assign" dropdown

Layout:
┌──────────────────────────────────────────────────────────────────────┐
│  Assigned Groups:                                                    │
│  • Group A  (assigned by: admin1, 2024-03-10)  [Remove ✕]          │
│  • Group B  (assigned by: admin1, 2024-03-12)  [Remove ✕]          │
│                                                                      │
│  [+ Assign Group]  →  <Select> from groups not already assigned      │
└──────────────────────────────────────────────────────────────────────┘

- Remove: calls useRemoveGroupPolicy with confirmation
- Assign: calls useAssignGroupPolicy
```

#### 7h. `PoliciesPage` (`src/pages/PoliciesPage.tsx`)

```
Layout:
┌──────────────────────────────────────────────────────────────────────┐
│  <h1>Policies</h1>                                                   │
│                                                                      │
│  <RiskModelList />                                                   │
│  {/* Accordion tree of risk models → policies */}                    │
│                                                                      │
│  {/* When a policy is selected, show detail in a side panel or       │
│      expand inline below the policy card */}                         │
│  {selectedPolicyId && (                                              │
│    <Sheet open onOpenChange={close}>                                 │
│      <SheetContent className="w-[600px]">                            │
│        <PolicyDetail policyId={selectedPolicyId} />                  │
│      </SheetContent>                                                 │
│    </Sheet>                                                          │
│  )}                                                                  │
└──────────────────────────────────────────────────────────────────────┘

State:
- selectedPolicyId (string | null) — which policy detail to show
- Synced to URL search param ?policy={id} for deep linking
```

---

### Step 8 — Admin Page (`/admin`)

The admin page is a tabbed view with three sections: Users, Groups, and Decision Statuses.

#### 8a. `UserTable` (`src/components/admin/UserTable.tsx`)

```
Props: { users: UserOut[]; total: number; offset: number; limit: number; onPageChange; onSelect }

Table columns:
| Username | Email | Active (badge) | Created | Actions |

- Active: green/red badge
- Actions: "Edit" button → opens UserForm, "Manage Groups" → opens UserGroupManager
- Click row → opens user detail in a Sheet
```

#### 8b. `UserForm` (`src/components/admin/UserForm.tsx`)

```
Props: { user?: UserOut; onSuccess: () => void }

Dialog form:
- Create mode (no user prop): username, email, password fields
- Edit mode (user prop): email, is_active toggle. Username is read-only.

Validation (Zod):
- username: required, 3-50 chars (create only)
- email: required, valid email
- password: required, min 8 chars (create only)
- is_active: boolean (edit only)

On submit:
- Create → useCreateUser()
- Edit → useUpdateUser()
- Toast on success/error
```

#### 8c. `UserGroupManager` (`src/components/admin/UserGroupManager.tsx`)

```
Props: { userId: string }

Data:
- useUserGroups(userId)
- useGroups() — for available groups dropdown

Layout:
┌──────────────────────────────────────────────────────────────────────┐
│  Group Memberships for {username}:                                   │
│  • Compliance Team     [Remove ✕]                                    │
│  • Senior Reviewers    [Remove ✕]                                    │
│                                                                      │
│  [+ Add to Group]  →  <Select> from groups user is not yet in        │
└──────────────────────────────────────────────────────────────────────┘
```

#### 8d. `GroupTable` (`src/components/admin/GroupTable.tsx`)

```
Props: { groups: GroupDetail[]; total; offset; limit; onPageChange; onSelect }

Table columns:
| Name | Roles (badges) | Members | Created | Actions |

- Roles: list of role name badges
- Members: count
- Actions: "Edit" → GroupForm, "Manage" → opens GroupDetailPanel in Sheet
```

#### 8e. `GroupForm` (`src/components/admin/GroupForm.tsx`)

```
Props: { group?: GroupOut; onSuccess: () => void }

Dialog form:
- Name: <Input> (required)
- Description: <Textarea> (optional)

Create → useCreateGroup(), Edit → useUpdateGroup()
```

#### 8f. `GroupDetailPanel` (`src/components/admin/GroupDetailPanel.tsx`)

```
Props: { groupId: string }

Data:
- useGroup(groupId) — detail with roles + member_count
- useGroupMembers(groupId) — list of members

Layout (Sheet slide-over):
┌──────────────────────────────────────────────────────────────────────┐
│  Group: {group.name}                                                 │
│  {group.description}                                                 │
│                                                                      │
│  ── Roles ──                                                         │
│  <RoleAssignmentManager groupId={groupId} />                        │
│                                                                      │
│  ── Members ({group.member_count}) ──                                │
│  {members.map(u => (                                                 │
│    <div>{u.username} ({u.email}) {u.is_active ? "Active" : "Inactive"}</div>
│  ))}                                                                 │
└──────────────────────────────────────────────────────────────────────┘
```

#### 8g. `RoleAssignmentManager` (`src/components/admin/RoleAssignmentManager.tsx`)

```
Props: { groupId: string }

Data:
- useGroup(groupId) — has .roles (role names)
- useRoles() — all available roles

Layout:
  Current roles as removable badges.
  "Add Role" dropdown shows roles not yet assigned.
  Add → useAssignRoleToGroup(), Remove → useRemoveRoleFromGroup()
```

#### 8h. `DecisionStatusTable` (`src/components/admin/DecisionStatusTable.tsx`)

```
Data: useDecisionStatuses() (from Phase 5 hook)

Read-only table:
| Name | Description | Terminal? | Display Order |

Terminal column: checkmark icon if is_terminal
Note: Decision status CRUD is not implemented in the backend yet —
this is a read-only informational view for now.
```

#### 8i. `AdminPage` (`src/pages/AdminPage.tsx`)

```
Layout:
┌──────────────────────────────────────────────────────────────────────┐
│  <h1>Administration</h1>                                             │
│                                                                      │
│  <Tabs defaultValue="users">                                         │
│    <TabsList>                                                        │
│      <Tab value="users">Users</Tab>                                  │
│      <Tab value="groups">Groups</Tab>                                │
│      <Tab value="decision-statuses">Decision Statuses</Tab>         │
│    </TabsList>                                                       │
│                                                                      │
│    <TabsContent value="users">                                       │
│      <div className="flex justify-between mb-4">                     │
│        <h2>Users</h2>                                                │
│        <Button onClick={openCreateUser}>+ Create User</Button>       │
│      </div>                                                          │
│      <UserTable users={users} ... />                                 │
│    </TabsContent>                                                    │
│                                                                      │
│    <TabsContent value="groups">                                      │
│      <div className="flex justify-between mb-4">                     │
│        <h2>Groups</h2>                                               │
│        <Button onClick={openCreateGroup}>+ Create Group</Button>     │
│      </div>                                                          │
│      <GroupTable groups={groups} ... />                               │
│    </TabsContent>                                                    │
│                                                                      │
│    <TabsContent value="decision-statuses">                           │
│      <DecisionStatusTable />                                         │
│    </TabsContent>                                                    │
│  </Tabs>                                                             │
│                                                                      │
│  {/* Sheet for group detail */}                                      │
│  {selectedGroupId && <Sheet ...><GroupDetailPanel /></Sheet>}         │
│  {/* Dialog for user/group forms */}                                 │
│  <UserForm ... />                                                    │
│  <GroupForm ... />                                                   │
└──────────────────────────────────────────────────────────────────────┘
```

---

### Step 9 — Audit Log Page (`/audit`)

#### 9a. `AuditFilterBar` (`src/components/audit/AuditFilterBar.tsx`)

```
Props: { filters: AuditLogParams; onChange: (filters) => void }

Layout:
┌──────────────────────────────────────────────────────────────────────┐
│  Actor: [________]  Alert ID: [________]                             │
│  Date from: [______]  Date to: [______]              [Clear filters] │
└──────────────────────────────────────────────────────────────────────┘

- Actor: text input for UUID (or could be a searchable dropdown)
- Alert ID: text input for UUID
- Date range: Popover + Calendar (reuse pattern)
- Filters sync to URL search params
```

#### 9b. `AuditLogTable` (`src/components/audit/AuditLogTable.tsx`)

```
Props: {
  entries: AuditLogEntry[];
  total: number;
  offset: number;
  limit: number;
  onPageChange: (offset: number) => void;
  onViewDetail: (entry: AuditLogEntry) => void;
}

Table columns:
| Timestamp | Action | Actor | Decision ID | IP Address | Detail |

- Timestamp: formatDateTime(entry.occurred_at)
- Action: entry.action (e.g., "decision_created")
- Actor: entry.actor_id (truncated UUID)
- Decision ID: link to alert detail (if we can resolve alert_id from decision_id)
- IP Address: entry.ip_address or "—"
- Detail: button that opens AuditDetailDialog

Pagination at bottom.
Empty state: "No audit entries match your filters."
```

#### 9c. `AuditDetailDialog` (`src/components/audit/AuditDetailDialog.tsx`)

```
Props: { entry: AuditLogEntry; open: boolean; onOpenChange }

Dialog showing the full audit entry:
┌──────────────────────────────────────────────────────────────────────┐
│  Audit Entry                                                         │
│                                                                      │
│  ID: {entry.id}                                                      │
│  Action: {entry.action}                                              │
│  Actor: {entry.actor_id}                                             │
│  Decision: {entry.decision_id}                                       │
│  Timestamp: {formatDateTime(entry.occurred_at)}                      │
│  IP: {entry.ip_address}                                              │
│  User Agent: {entry.user_agent}                                      │
│                                                                      │
│  ── Old Values ──                                                    │
│  <pre>{JSON.stringify(entry.old_values, null, 2)}</pre>              │
│                                                                      │
│  ── New Values ──                                                    │
│  <pre>{JSON.stringify(entry.new_values, null, 2)}</pre>              │
└──────────────────────────────────────────────────────────────────────┘

Use <ScrollArea> if JSON content is long.
```

#### 9d. `AuditPage` (`src/pages/AuditPage.tsx`)

```
State:
- filters (actor_id, alert_id, date_from, date_to) synced to URL
- offset synced to URL
- selectedEntry (for detail dialog)

Data:
- useAuditLog({ ...filters, offset, limit: 50 })

Layout:
┌──────────────────────────────────────────────────────────────────────┐
│  <h1>Audit Log</h1>                                                  │
│                                                                      │
│  <AuditFilterBar filters={filters} onChange={setFilters} />          │
│                                                                      │
│  <AuditLogTable entries={data.items} total={data.total}              │
│    offset={offset} limit={50} onPageChange={setOffset}              │
│    onViewDetail={setSelectedEntry} />                                │
│                                                                      │
│  <AuditDetailDialog entry={selectedEntry} open={!!selectedEntry}     │
│    onOpenChange={() => setSelectedEntry(null)} />                    │
└──────────────────────────────────────────────────────────────────────┘
```

---

### Step 10 — Queue Management Enhancements

Enhance `QueueDetailPage` and `QueuesPage` with supervisor management capabilities.

#### 10a. `CreateQueueDialog` (`src/components/queues/CreateQueueDialog.tsx`)

```
Props: { open, onOpenChange, onSuccess }

Dialog form:
- Name: <Input> (required)
- Description: <Textarea> (optional)
- Policy: <Select> populated from usePolicies() — selects which policy the queue is for

On submit: useCreateQueue()
```

#### 10b. `CreateBatchDialog` (`src/components/queues/CreateBatchDialog.tsx`)

```
Props: { queueId, open, onOpenChange, onSuccess }

Dialog form:
- Name: <Input> (optional — "Batch 1", etc.)

On submit: useCreateBatch(queueId)
```

#### 10c. `BatchAssignDialog` (`src/components/queues/BatchAssignDialog.tsx`)

```
Props: { queueId, batchId, open, onOpenChange, onSuccess }

Dialog form:
- Reviewer: <Select> populated from useUsers() — shows active users with reviewer+ role

On submit: useUpdateBatch(queueId, { batchId, assigned_to: selectedUserId })
```

#### 10d. `AddItemDialog` (`src/components/queues/AddItemDialog.tsx`)

```
Props: { queueId, batchId, open, onOpenChange, onSuccess }

Dialog form:
- Alert ID: <Input> (UUID) — or searchable <Command> that searches alerts
- Position: <Input type="number">

On submit: useAddItemToBatch(queueId, batchId)
```

#### 10e. `BatchTable` (`src/components/queues/BatchTable.tsx`)

```
Props: { batches: BatchOut[], queueId: string, isSupervisor: boolean }

Table columns:
| Name | Status (badge) | Assigned To | Items | Created | Actions |

Actions (supervisor only):
- "Assign" → opens BatchAssignDialog
- "Add Items" → opens AddItemDialog
- Status update → dropdown to change status
```

#### 10f. Enhance `QueueDetailPage`

Replace the current placeholder batch management note with the actual batch table and management controls:

```
Layout (supervisor view):
┌──────────────────────────────────────────────────────────────────────┐
│  ← Back to Queues                                                    │
│                                                                      │
│  <h1>{queue.name}</h1>                                               │
│  {queue.description}                                                 │
│  Batches: {queue.batch_count}  Items: {queue.total_items}            │
│                                                                      │
│  {isSupervisor && <Button onClick={openCreateBatch}>+ New Batch</Button>}
│                                                                      │
│  <BatchTable batches={batches} queueId={queue.id}                    │
│    isSupervisor={isSupervisor} />                                    │
│                                                                      │
│  {selectedBatchId && <BatchItemList queueId batchId />}              │
└──────────────────────────────────────────────────────────────────────┘
```

#### 10g. Enhance `QueuesPage` (supervisor tab)

Add a "Create Queue" button on the supervisor's "All Queues" tab:

```
{isSupervisor && <Button onClick={openCreateQueue}>+ New Queue</Button>}
```

---

### Step 11 — Export Button Component

#### `ExportButton` (`src/components/export/ExportButton.tsx`)

```
Props: {
  type: "alerts" | "messages";
  params: Record<string, string>;
}

Renders a dropdown button:
  [⬇ Export ▾]
    → CSV
    → JSON

Behavior:
1. Build export URL using buildExportUrl()
2. Fetch with auth header (access token)
3. Create a blob URL and trigger download via hidden <a> element
4. Show loading state while download is in progress

This component is placed on:
- AlertsPage (supervisor+) — exports current filtered alert set
- MessagesPage (supervisor+) — exports current search results
```

---

### Step 12 — Update Routes in App.tsx

Replace all `<ComingSoon>` placeholders with actual page components:

```tsx
// Before (Phase 5):
<Route path="/messages" element={<ComingSoon label="Messages" />} />
<Route path="/policies" element={<ComingSoon label="Policies" />} />
<Route path="/admin" element={<ComingSoon label="Admin" />} />
<Route path="/audit" element={<ComingSoon label="Audit Log" />} />

// After (Phase 6):
<Route path="/messages" element={<MessagesPage />} />
<Route path="/messages/:index/:docId" element={<MessageDetailPage />} />
<Route path="/policies" element={<PoliciesPage />} />
<Route path="/admin" element={<AdminPage />} />
<Route path="/audit" element={<AuditPage />} />
```

Also remove the `ComingSoon` component since it is no longer used.

Add the export button to `AlertsPage` (for supervisor+):

```tsx
{hasRole(roles, "supervisor") && (
  <ExportButton type="alerts" params={{ severity: filters.severity, status: filters.status }} />
)}
```

---

### Step 13 — Tests

#### Frontend Tests (Vitest + Testing Library)

| Test File | What it Covers |
|---|---|
| `tests/MessageSearchForm.test.tsx` | Filter inputs update params, submit triggers search, clear resets |
| `tests/MessageSearchResults.test.tsx` | Renders result cards with highlights, pagination, click navigates |
| `tests/MessagesPage.test.tsx` | Full search flow: enter query → see results → click result |
| `tests/MessageDetailPage.test.tsx` | Renders message content, handles loading/error |
| `tests/PolicyList.test.tsx` | Accordion renders risk models/policies, admin sees create button |
| `tests/RuleTable.test.tsx` | Table renders rules, active toggle calls mutation, delete confirms |
| `tests/RuleForm.test.tsx` | Form validation, create/edit modes, submit calls correct mutation |
| `tests/UserTable.test.tsx` | Renders user list, pagination, action buttons |
| `tests/UserForm.test.tsx` | Create mode shows password field, edit mode shows is_active toggle |
| `tests/GroupTable.test.tsx` | Renders groups with role badges and member counts |
| `tests/AuditLogTable.test.tsx` | Renders entries, detail button opens dialog, pagination |
| `tests/AuditFilterBar.test.tsx` | Filter changes update URL params, clear resets |
| `tests/ExportButton.test.tsx` | Dropdown shows CSV/JSON options, triggers download |
| `tests/CreateQueueDialog.test.tsx` | Form validates, submit creates queue |
| `tests/BatchTable.test.tsx` | Renders batches, supervisor sees action buttons |

**Test setup:**
- Mock `apiFetch` at the module level using `vi.mock("@/api/client")`
- Wrap components in `QueryClientProvider` + `MemoryRouter`
- Use `@testing-library/user-event` for interactions
- Use `waitFor` for async state updates
- Test role-awareness by setting the auth store state before rendering

---

## 6. Implementation Order (Recommended)

Work in this order to stay unblocked and allow incremental testing. The six workstreams can be parallelized across developers.

| # | Task | Depends On | Est. Complexity |
|---|---|---|---|
| **Foundation** | | | |
| 1 | Install shadcn/ui components | — | Low |
| 2 | Add new types to `lib/types.ts` | — | Low |
| 3 | Set up Toaster (sonner) in `main.tsx` | Step 1 | Low |
| **Workstream A: Messages** | | | |
| 4 | Extend `api/messages.ts` (searchMessages, getMessage) | — | Low |
| 5 | Create `hooks/useMessages.ts` | Step 4 | Low |
| 6 | `MessageSearchForm` component | Step 1 | Medium |
| 7 | `MessageHighlight` component | — | Low |
| 8 | `MessageSearchResults` component | Step 7 | Medium |
| 9 | `MessagesPage` | Steps 5, 6, 8 | Medium |
| 10 | `LinkedAlerts` component | — | Low |
| 11 | `MessageDetailPage` | Steps 5, 10 | Medium |
| **Workstream B: Policies** | | | |
| 12 | Create `api/policies.ts` + `api/risk-models.ts` | — | Low |
| 13 | Create `hooks/usePolicies.ts` + `hooks/useRiskModels.ts` | Step 12 | Medium |
| 14 | `RiskModelList` + `RiskModelForm` | Steps 1, 13 | Medium |
| 15 | `PolicyList` + `PolicyForm` | Steps 1, 13 | Medium |
| 16 | `RuleTable` + `RuleForm` | Steps 1, 13 | High |
| 17 | `GroupPolicyManager` | Step 13 | Medium |
| 18 | `PolicyDetail` | Steps 16, 17 | Medium |
| 19 | `PoliciesPage` | Steps 14, 15, 18 | Medium |
| **Workstream C: Admin** | | | |
| 20 | Create `api/users.ts`, `api/groups.ts`, `api/roles.ts` | — | Low |
| 21 | Create `hooks/useUsers.ts`, `hooks/useGroups.ts`, `hooks/useRoles.ts` | Step 20 | Medium |
| 22 | `UserTable` + `UserForm` | Steps 1, 21 | Medium |
| 23 | `UserGroupManager` | Step 21 | Medium |
| 24 | `GroupTable` + `GroupForm` | Steps 1, 21 | Medium |
| 25 | `GroupDetailPanel` + `RoleAssignmentManager` | Steps 21, 24 | Medium |
| 26 | `DecisionStatusTable` | — | Low |
| 27 | `AdminPage` | Steps 22–26 | High |
| **Workstream D: Audit** | | | |
| 28 | Create `api/audit.ts` | — | Low |
| 29 | Create `hooks/useAuditLog.ts` | Step 28 | Low |
| 30 | `AuditFilterBar` | Step 1 | Low |
| 31 | `AuditLogTable` | Step 1 | Medium |
| 32 | `AuditDetailDialog` | Step 1 | Low |
| 33 | `AuditPage` | Steps 29–32 | Medium |
| **Workstream E: Queue Management** | | | |
| 34 | Extend `api/queues.ts` (create/assign mutations) | — | Low |
| 35 | Extend `hooks/useQueues.ts` (mutation hooks) | Step 34 | Low |
| 36 | `CreateQueueDialog` + `CreateBatchDialog` | Steps 1, 35 | Medium |
| 37 | `BatchAssignDialog` + `AddItemDialog` | Steps 1, 35 | Medium |
| 38 | `BatchTable` | Steps 1, 35 | Medium |
| 39 | Enhance `QueueDetailPage` + `QueuesPage` | Steps 36–38 | Medium |
| **Workstream F: Export** | | | |
| 40 | Create `api/export.ts` | — | Low |
| 41 | `ExportButton` | Step 40 | Medium |
| 42 | Add export buttons to AlertsPage + MessagesPage | Step 41 | Low |
| **Finalize** | | | |
| 43 | Update `App.tsx` routes | Steps 9, 11, 19, 27, 33, 39 | Low |
| 44 | Remove `ComingSoon` component | Step 43 | Low |
| 45 | Write tests | All above | High |

---

## 7. Files Summary

### New Files (~45)

```
# API modules (8)
src/api/policies.ts
src/api/risk-models.ts
src/api/users.ts
src/api/groups.ts
src/api/roles.ts
src/api/audit.ts
src/api/export.ts

# Hooks (7)
src/hooks/useMessages.ts
src/hooks/usePolicies.ts
src/hooks/useRiskModels.ts
src/hooks/useUsers.ts
src/hooks/useGroups.ts
src/hooks/useRoles.ts
src/hooks/useAuditLog.ts

# Pages (5)
src/pages/MessagesPage.tsx
src/pages/MessageDetailPage.tsx
src/pages/PoliciesPage.tsx
src/pages/AdminPage.tsx
src/pages/AuditPage.tsx

# Components — messages (4)
src/components/messages/MessageSearchForm.tsx
src/components/messages/MessageSearchResults.tsx
src/components/messages/MessageHighlight.tsx
src/components/messages/LinkedAlerts.tsx

# Components — policies (8)
src/components/policies/RiskModelList.tsx
src/components/policies/RiskModelForm.tsx
src/components/policies/PolicyList.tsx
src/components/policies/PolicyForm.tsx
src/components/policies/PolicyDetail.tsx
src/components/policies/RuleTable.tsx
src/components/policies/RuleForm.tsx
src/components/policies/GroupPolicyManager.tsx

# Components — admin (8)
src/components/admin/UserTable.tsx
src/components/admin/UserForm.tsx
src/components/admin/UserGroupManager.tsx
src/components/admin/GroupTable.tsx
src/components/admin/GroupForm.tsx
src/components/admin/GroupDetailPanel.tsx
src/components/admin/RoleAssignmentManager.tsx
src/components/admin/DecisionStatusTable.tsx

# Components — audit (3)
src/components/audit/AuditLogTable.tsx
src/components/audit/AuditFilterBar.tsx
src/components/audit/AuditDetailDialog.tsx

# Components — queues (5)
src/components/queues/CreateQueueDialog.tsx
src/components/queues/CreateBatchDialog.tsx
src/components/queues/BatchAssignDialog.tsx
src/components/queues/AddItemDialog.tsx
src/components/queues/BatchTable.tsx

# Components — export (1)
src/components/export/ExportButton.tsx
```

### Modified Files (7)

```
src/api/messages.ts          — add searchMessages, getMessage
src/api/queues.ts            — add createQueue, createBatch, updateBatch, addItemToBatch
src/hooks/useQueues.ts       — add mutation hooks (useCreateQueue, etc.)
src/lib/types.ts             — add ESMessageHit, MessageSearchResponse, PolicyDetail, RiskModelDetail, GroupPolicyOut, GroupDetail, UserWithRoles; update AuditLogEntry
src/App.tsx                  — replace ComingSoon with real pages, add /messages/:index/:docId route, remove ComingSoon component
src/main.tsx                 — add <Toaster /> from sonner
src/pages/QueueDetailPage.tsx — add batch management (BatchTable, create/assign/add dialogs)
src/pages/QueuesPage.tsx     — add "Create Queue" button for supervisors
src/pages/AlertsPage.tsx     — add ExportButton for supervisors
```

### New shadcn/ui Components (~7)

```
src/components/ui/switch.tsx
src/components/ui/sheet.tsx
src/components/ui/accordion.tsx
src/components/ui/alert-dialog.tsx
src/components/ui/form.tsx
src/components/ui/sonner.tsx
src/components/ui/breadcrumb.tsx
```

---

## 8. Acceptance Criteria

Phase 6 is complete when:

1. **Messages page** loads at `/messages`, displays a search form with full-text query and filters (channel, direction, participant, date range, sentiment, risk score), returns paginated results with highlighted matches, and navigates to message detail on click
2. **Message detail page** loads at `/messages/:index/:docId`, shows the full message (body, participants, attachments, audio player, enrichments) using the existing `MessageDisplay` component, and lists any linked alerts
3. **Policies page** loads at `/policies`, displays an accordion tree of risk models → policies. Reviewers see read-only views. Admins can create/edit risk models and policies, create/edit/deactivate rules, and manage group-policy assignments
4. **Rule management** works end-to-end: admin can create a rule (name, KQL, severity), edit it, toggle active/inactive, and soft-delete it. The rule table refreshes after each mutation
5. **Admin page** loads at `/admin` with three tabs: Users, Groups, Decision Statuses. Admin can create/edit users, manage group memberships, create/edit groups, assign/remove roles from groups
6. **Audit log page** loads at `/audit`, displays a paginated table of audit entries with filters (actor, alert, date range). Clicking an entry opens a detail dialog showing old_values/new_values JSON
7. **Queue management** is fully functional for supervisors: create queues, create batches within queues, assign batches to reviewers, add alerts to batches, monitor batch status
8. **Export** works for supervisors: export buttons on alerts and messages pages trigger CSV/JSON downloads with the current filter set
9. **All pages** handle loading states (skeletons), error states (error cards with retry), and empty states gracefully
10. **Route guards** enforce role-based access — admin pages are not accessible to reviewers/supervisors, audit page is not accessible to reviewers
11. **URL-synced state** on messages search and audit log pages allow sharing filtered views via URL
12. **Toasts** provide feedback on all CRUD operations (success/error)
13. **No regressions** — dashboard, login, alerts, alert detail, and queue pages from Phase 4-5 continue to work
14. **All `<ComingSoon>` placeholders are removed** — every sidebar link leads to a functional page
15. **Frontend builds** without TypeScript errors (`npm run build` succeeds)

---

## 9. Open Questions

1. **Message → Alert linking**: The backend doesn't expose a direct "find alerts by es_document_id" filter on `GET /alerts`. For the `LinkedAlerts` component on the message detail page, we may need to add an `es_document_id` filter parameter to the alerts endpoint, or omit linked alerts in Phase 6 and add it in Phase 7.

2. **KQL syntax highlighting**: Should the rule editor have syntax highlighting for KQL? This would require a code editor component (like CodeMirror or Monaco). For Phase 6, a plain `<Textarea>` with monospace font is sufficient. Syntax highlighting can be added as a Phase 7 enhancement.

3. **Batch auto-population**: The queue batch management currently only supports manually adding alerts. Auto-populating a batch with alerts matching a policy's rules would require a new backend endpoint. Defer to Phase 7.

4. **Decision status CRUD**: The admin page shows decision statuses as read-only. Full CRUD for decision statuses (create, reorder, deactivate) would require new backend endpoints. Defer to Phase 7.

5. **User search in batch assignment**: The `BatchAssignDialog` needs a list of users with reviewer+ role. The current `GET /users` endpoint returns all users without role filtering. A simple approach: fetch all users and filter client-side (acceptable for small user bases). For larger deployments, a `role` filter parameter should be added to the backend.
