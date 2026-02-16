# Phase 5 — Alert Review UI (Detailed Plan)

## 1. Overview

Phase 5 delivers the primary reviewer workflow: browsing, filtering, and reviewing alerts end-to-end. It replaces the `<ComingSoon>` placeholders on three routes (`/alerts`, `/alerts/:id`, `/queues`) with fully functional pages backed by the Phase 2–3 backend APIs.

**Goal:** A reviewer can log in, see their assigned alerts or browse all alerts, open an alert detail page with the full linked message, and submit a decision — all without leaving the browser.

**Scope:**

| Route | Page | Role | What it does |
|---|---|---|---|
| `/alerts` | AlertsPage | reviewer+ | Sortable, filterable, paginated alert table |
| `/alerts/:id` | AlertDetailPage | reviewer+ | Alert metadata + linked ES message + decision history + decision form |
| `/queues` | QueuesPage | reviewer (own batches) / supervisor (all queues) | My-queue batch list + navigate items in order |
| `/queues/:id` | QueueDetailPage | reviewer+ | Queue batches, items, progress |

**Dependencies:** All backend endpoints used by this phase are already implemented (Phase 2):
- `GET /api/v1/alerts` — paginated alert list with severity/status/rule filters
- `GET /api/v1/alerts/{id}` — alert detail with ES message, rule name, policy name
- `PATCH /api/v1/alerts/{id}/status` — update alert status
- `POST /api/v1/alerts/{id}/decisions` — submit decision
- `GET /api/v1/alerts/{id}/decisions` — decision history
- `GET /api/v1/decision-statuses` — available decision statuses
- `GET /api/v1/messages/{index}/{doc_id}/audio` — pre-signed S3 URL for audio
- `GET /api/v1/queues`, `GET /api/v1/queues/{id}` — queue list/detail
- `GET /api/v1/queues/{id}/batches/{bid}/items` — batch items
- `GET /api/v1/my-queue` — current user's assigned batches

---

## 2. New shadcn/ui Components to Install

These components from `shadcn/ui` are needed for the alert review UI and are **not yet installed** (existing: button, card, input, label, separator, avatar, badge, dropdown-menu, dialog, tooltip, select).

| Component | Used By | Purpose |
|---|---|---|
| **table** | AlertTable | Styled table primitives (Table, TableHead, TableRow, TableCell, etc.) |
| **pagination** | AlertTable | Page navigation at bottom of alert list |
| **textarea** | DecisionForm | Multi-line comment input for decision submission |
| **tabs** | AlertDetailPage | Tab layout for message body / enrichments / decision history |
| **skeleton** | AlertTable, AlertDetailPage | Loading placeholders |
| **popover** | AlertFilters | Date picker popover, filter dropdowns |
| **calendar** | AlertFilters | Date range picker for filtering alerts by date |
| **command** | AlertFilters | Searchable select for participants |
| **scroll-area** | DecisionTimeline | Scrollable decision history |

Install command:
```bash
npx shadcn@latest add table pagination textarea tabs skeleton popover calendar command scroll-area
```

---

## 3. New Files to Create

### 3.1 API Modules (`src/api/`)

| File | Functions | Backend Endpoint |
|---|---|---|
| `src/api/alerts.ts` (extend) | `getAlerts(params)`, `getAlert(id)`, `updateAlertStatus(id, status)` | `GET /alerts`, `GET /alerts/{id}`, `PATCH /alerts/{id}/status` |
| `src/api/decisions.ts` (new) | `getDecisions(alertId)`, `createDecision(alertId, body)`, `getDecisionStatuses()` | `GET /alerts/{id}/decisions`, `POST /alerts/{id}/decisions`, `GET /decision-statuses` |
| `src/api/queues.ts` (new) | `getQueues(params)`, `getQueue(id)`, `getBatchItems(queueId, batchId)`, `getMyQueue()` | `GET /queues`, `GET /queues/{id}`, `GET /queues/{id}/batches/{bid}/items`, `GET /my-queue` |
| `src/api/messages.ts` (new) | `getAudioUrl(index, docId)` | `GET /messages/{index}/{doc_id}/audio` |

### 3.2 TanStack Query Hooks (`src/hooks/`)

| File | Hooks | Query Keys |
|---|---|---|
| `src/hooks/useAlerts.ts` (extend) | `useAlerts(params)`, `useAlert(id)`, `useUpdateAlertStatus()` | `["alerts", params]`, `["alerts", id]` |
| `src/hooks/useDecisions.ts` (new) | `useDecisions(alertId)`, `useCreateDecision()`, `useDecisionStatuses()` | `["decisions", alertId]`, `["decision-statuses"]` |
| `src/hooks/useQueues.ts` (new) | `useQueues(params)`, `useQueue(id)`, `useBatchItems(queueId, batchId)`, `useMyQueue()` | `["queues", params]`, `["queues", id]`, `["batches", batchId, "items"]`, `["my-queue"]` |

### 3.3 Pages (`src/pages/`)

| File | Role | Description |
|---|---|---|
| `src/pages/AlertsPage.tsx` (new) | reviewer+ | Full alert list with filters, sort, pagination |
| `src/pages/AlertDetailPage.tsx` (new) | reviewer+ | Alert + message + decisions + decision form |
| `src/pages/QueuesPage.tsx` (new) | reviewer+ | My-queue for reviewers, all-queues for supervisors |
| `src/pages/QueueDetailPage.tsx` (new) | reviewer+ | Queue detail with batches and items |

### 3.4 Components (`src/components/`)

| File | Props | Description |
|---|---|---|
| **alerts/** | | |
| `AlertTable.tsx` | `alerts, total, offset, limit, sorting, onSort, onPageChange` | TanStack Table with sortable columns: severity, status, name, rule, channel, date |
| `AlertFilters.tsx` | `filters, onChange` | Filter bar: severity multi-select, status multi-select, date range picker |
| `AlertSeverityBadge.tsx` | `severity` | Color-coded badge (critical=red, high=orange, medium=yellow, low=blue) |
| `AlertStatusBadge.tsx` | `status` | Color-coded badge (open=blue, in_review=yellow, closed=green) |
| `AlertMetadataCard.tsx` | `alert` | Card showing alert name, severity, status, rule, policy, timestamps |
| `DecisionForm.tsx` | `alertId, onSuccess` | Status dropdown (from decision-statuses) + comment textarea + submit |
| `DecisionTimeline.tsx` | `decisions` | Chronological list of past decisions with status, reviewer, comment, timestamp |
| **messages/** | | |
| `MessageDisplay.tsx` | `message` | Renders body_text/transcript, participants, attachments, enrichments |
| `ParticipantList.tsx` | `participants` | List of participants with role badges |
| `AudioPlayer.tsx` | `esIndex, docId` | HTML5 audio player that fetches pre-signed URL on mount |
| `EnrichmentPanel.tsx` | `message` | Entities, sentiment, risk score, matched policies |
| **queues/** | | |
| `MyQueueList.tsx` | — | Current user's assigned batches with progress |
| `BatchCard.tsx` | `batch` | Card showing batch name, status, item count, assignment |
| `BatchItemList.tsx` | `queueId, batchId` | Ordered list of alerts in a batch, linking to alert detail |
| `BatchProgress.tsx` | `decided, total` | Visual progress bar (X of Y reviewed) |

---

## 4. Detailed Implementation Steps

### Step 1 — Install shadcn/ui Components

```bash
cd ui/frontend
npx shadcn@latest add table pagination textarea tabs skeleton popover calendar command scroll-area
```

Verify all components land in `src/components/ui/`.

---

### Step 2 — API Modules

#### 2a. Extend `src/api/alerts.ts`

Add to the existing file (which currently only has `getAlertStats`):

```typescript
import type {
  AlertOut,
  AlertWithMessage,
  PaginatedResponse,
} from "@/lib/types";

export interface AlertListParams {
  severity?: string;
  status?: string;
  rule_id?: string;
  offset?: number;
  limit?: number;
}

export async function getAlerts(
  params: AlertListParams = {},
): Promise<PaginatedResponse<AlertOut>> {
  const searchParams = new URLSearchParams();
  if (params.severity) searchParams.set("severity", params.severity);
  if (params.status) searchParams.set("status", params.status);
  if (params.rule_id) searchParams.set("rule_id", params.rule_id);
  searchParams.set("offset", String(params.offset ?? 0));
  searchParams.set("limit", String(params.limit ?? 50));

  return apiFetch<PaginatedResponse<AlertOut>>(
    `/alerts?${searchParams.toString()}`,
  );
}

export async function getAlert(id: string): Promise<AlertWithMessage> {
  return apiFetch<AlertWithMessage>(`/alerts/${id}`);
}

export async function updateAlertStatus(
  id: string,
  status: string,
): Promise<AlertOut> {
  return apiFetch<AlertOut>(`/alerts/${id}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}
```

#### 2b. Create `src/api/decisions.ts`

```typescript
import { apiFetch } from "./client";
import type { DecisionOut, DecisionStatusOut } from "@/lib/types";

export async function getDecisions(alertId: string): Promise<DecisionOut[]> {
  return apiFetch<DecisionOut[]>(`/alerts/${alertId}/decisions`);
}

export async function createDecision(
  alertId: string,
  body: { status_id: string; comment?: string },
): Promise<DecisionOut> {
  return apiFetch<DecisionOut>(`/alerts/${alertId}/decisions`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function getDecisionStatuses(): Promise<DecisionStatusOut[]> {
  return apiFetch<DecisionStatusOut[]>("/decision-statuses");
}
```

#### 2c. Create `src/api/queues.ts`

```typescript
import { apiFetch } from "./client";
import type {
  QueueOut,
  QueueDetail,
  BatchOut,
  PaginatedResponse,
} from "@/lib/types";

export interface QueueItemOut {
  id: string;
  batch_id: string;
  alert_id: string;
  position: number;
  created_at: string;
}

export async function getQueues(
  params: { offset?: number; limit?: number } = {},
): Promise<PaginatedResponse<QueueOut>> {
  const sp = new URLSearchParams();
  sp.set("offset", String(params.offset ?? 0));
  sp.set("limit", String(params.limit ?? 50));
  return apiFetch(`/queues?${sp.toString()}`);
}

export async function getQueue(id: string): Promise<QueueDetail> {
  return apiFetch(`/queues/${id}`);
}

export async function getBatchItems(
  queueId: string,
  batchId: string,
): Promise<QueueItemOut[]> {
  return apiFetch(`/queues/${queueId}/batches/${batchId}/items`);
}

export async function getMyQueue(): Promise<BatchOut[]> {
  return apiFetch("/my-queue");
}
```

#### 2d. Create `src/api/messages.ts`

```typescript
import { apiFetch } from "./client";

export interface AudioUrlResponse {
  url: string;
  expires_in: number;
}

export async function getAudioUrl(
  index: string,
  docId: string,
): Promise<AudioUrlResponse> {
  return apiFetch(`/messages/${index}/${docId}/audio`);
}
```

---

### Step 3 — TanStack Query Hooks

#### 3a. Extend `src/hooks/useAlerts.ts`

Add hooks for alert list, single alert, and status mutation:

```typescript
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getAlertStats,
  getAlerts,
  getAlert,
  updateAlertStatus,
} from "@/api/alerts";
import type { AlertListParams } from "@/api/alerts";

export function useAlertStats() {
  return useQuery({
    queryKey: ["alerts", "stats"],
    queryFn: getAlertStats,
    refetchInterval: 60_000,
  });
}

export function useAlerts(params: AlertListParams) {
  return useQuery({
    queryKey: ["alerts", "list", params],
    queryFn: () => getAlerts(params),
  });
}

export function useAlert(id: string) {
  return useQuery({
    queryKey: ["alerts", id],
    queryFn: () => getAlert(id),
    enabled: !!id,
  });
}

export function useUpdateAlertStatus() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      updateAlertStatus(id, status),
    onSuccess: (_data, { id }) => {
      void queryClient.invalidateQueries({ queryKey: ["alerts", id] });
      void queryClient.invalidateQueries({ queryKey: ["alerts", "list"] });
      void queryClient.invalidateQueries({ queryKey: ["alerts", "stats"] });
    },
  });
}
```

#### 3b. Create `src/hooks/useDecisions.ts`

```typescript
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getDecisions,
  createDecision,
  getDecisionStatuses,
} from "@/api/decisions";

export function useDecisions(alertId: string) {
  return useQuery({
    queryKey: ["decisions", alertId],
    queryFn: () => getDecisions(alertId),
    enabled: !!alertId,
  });
}

export function useCreateDecision(alertId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { status_id: string; comment?: string }) =>
      createDecision(alertId, body),
    onSuccess: () => {
      // Refresh decision history, alert detail (status may have changed), and list
      void queryClient.invalidateQueries({ queryKey: ["decisions", alertId] });
      void queryClient.invalidateQueries({ queryKey: ["alerts", alertId] });
      void queryClient.invalidateQueries({ queryKey: ["alerts", "list"] });
      void queryClient.invalidateQueries({ queryKey: ["alerts", "stats"] });
    },
  });
}

export function useDecisionStatuses() {
  return useQuery({
    queryKey: ["decision-statuses"],
    queryFn: getDecisionStatuses,
    staleTime: 10 * 60 * 1000, // statuses rarely change — 10 min
  });
}
```

#### 3c. Create `src/hooks/useQueues.ts`

```typescript
import { useQuery } from "@tanstack/react-query";
import { getQueues, getQueue, getBatchItems, getMyQueue } from "@/api/queues";

export function useQueues(params: { offset?: number; limit?: number } = {}) {
  return useQuery({
    queryKey: ["queues", "list", params],
    queryFn: () => getQueues(params),
  });
}

export function useQueue(id: string) {
  return useQuery({
    queryKey: ["queues", id],
    queryFn: () => getQueue(id),
    enabled: !!id,
  });
}

export function useBatchItems(queueId: string, batchId: string) {
  return useQuery({
    queryKey: ["batches", batchId, "items"],
    queryFn: () => getBatchItems(queueId, batchId),
    enabled: !!queueId && !!batchId,
  });
}

export function useMyQueue() {
  return useQuery({
    queryKey: ["my-queue"],
    queryFn: getMyQueue,
    refetchInterval: 30_000, // check for new assignments every 30s
  });
}
```

---

### Step 4 — Shared Alert Components

#### 4a. `AlertSeverityBadge` (`src/components/alerts/AlertSeverityBadge.tsx`)

A small badge component reused across the alert table and detail page. Maps severity levels to color variants using the existing `SEVERITY_COLORS` constant from `lib/constants.ts`.

```
Props: { severity: Severity }
Renders: <Badge variant={severity}>{severity}</Badge>
```

#### 4b. `AlertStatusBadge` (`src/components/alerts/AlertStatusBadge.tsx`)

Similar badge for alert status. Color mapping:
- `open` → blue/outline
- `in_review` → yellow/warning
- `closed` → green/success

```
Props: { status: AlertStatus }
Renders: <Badge variant={status}>{label}</Badge>
```

---

### Step 5 — Alerts Page (`/alerts`)

#### 5a. `AlertFilters` (`src/components/alerts/AlertFilters.tsx`)

Filter bar rendered above the alert table.

```
Props: {
  filters: { severity?: string; status?: string; dateFrom?: string; dateTo?: string };
  onChange: (filters) => void;
}

Layout:
┌────────────────────────────────────────────────────────────────────────────┐
│  Severity: [All ▾]  Status: [All ▾]  Date range: [From] → [To]  [Clear] │
└────────────────────────────────────────────────────────────────────────────┘

Components used:
- <Select> for severity (options from SEVERITY_LEVELS constant)
- <Select> for status (options from ALERT_STATUSES constant)
- <Popover> + <Calendar> for date range
- <Button variant="ghost"> for "Clear filters"
```

Filters update URL search params so that filtered views are shareable/bookmarkable. Use `useSearchParams` from React Router.

#### 5b. `AlertTable` (`src/components/alerts/AlertTable.tsx`)

Headless TanStack Table with the following columns:

| Column | Sortable | Content |
|---|---|---|
| Severity | yes | `<AlertSeverityBadge>` |
| Name | yes | Alert name (text, truncated) |
| Status | yes | `<AlertStatusBadge>` |
| Rule | no | `rule_name` (if present) |
| Created | yes | Formatted timestamp via `formatRelative()` |

```
Props: {
  data: AlertOut[];
  total: number;
  offset: number;
  limit: number;
  onPageChange: (offset: number) => void;
}

Behavior:
- Click row → navigate(`/alerts/${alert.id}`)
- Sortable column headers (client-side sort within current page)
- Bottom: <Pagination> showing "Page X of Y" with prev/next buttons
- Empty state: "No alerts match your filters" with link to clear filters
- Loading state: <Skeleton> rows (6 rows of skeleton cells)
```

#### 5c. `AlertsPage` (`src/pages/AlertsPage.tsx`)

Orchestrates filters, table, and data fetching.

```
State:
- filters (severity, status) synced to URL search params
- offset (pagination) synced to URL search params

Data:
- useAlerts({ severity, status, offset, limit: 50 })

Layout:
┌──────────────────────────────────────────────────────────────────────┐
│  <h1>Alerts</h1>                                                     │
│                                                                      │
│  <AlertFilters filters={...} onChange={...} />                       │
│                                                                      │
│  <AlertTable data={alerts} total={total} offset={offset}            │
│    limit={50} onPageChange={setOffset} />                            │
└──────────────────────────────────────────────────────────────────────┘

Error state: Show error card with retry button
Loading state: Skeleton table
```

---

### Step 6 — Alert Detail Page (`/alerts/:id`)

This is the most complex page — it combines data from PG (alert metadata) and ES (linked message), and provides the decision submission workflow.

#### 6a. `AlertMetadataCard` (`src/components/alerts/AlertMetadataCard.tsx`)

```
Props: { alert: AlertWithMessage }

Layout:
┌──────────────────────────────────────────────────────────────────────┐
│  Alert: {alert.name}                              <SeverityBadge>   │
│                                                                      │
│  Status:   <StatusBadge>                                             │
│  Rule:     {alert.rule_name}                                         │
│  Policy:   {alert.policy_name}                                       │
│  Created:  {formatDateTime(alert.created_at)}                        │
│  Message:  {alert.es_document_ts ? formatDateTime(...) : "—"}        │
└──────────────────────────────────────────────────────────────────────┘
```

Uses `<Card>`, `<Badge>`, and layout utilities.

#### 6b. `MessageDisplay` (`src/components/messages/MessageDisplay.tsx`)

Renders the full ES message content. Adapts to the message channel.

```
Props: { message: ESMessage; esIndex: string }

Layout:
┌──────────────────────────────────────────────────────────────────────┐
│  Channel: {message.channel}       Direction: {message.direction}     │
│  Timestamp: {formatDateTime(message.timestamp)}                      │
│                                                                      │
│  ── Participants ──                                                  │
│  <ParticipantList participants={message.participants} />             │
│                                                                      │
│  ── Content ──                                                       │
│  {message.body_text && <div>{body_text}</div>}                       │
│  {message.transcript && <div>Transcript: {transcript}</div>}         │
│  {message.translated_text && <div>Translation: {translated}</div>}   │
│  {message.audio_ref && <AudioPlayer ... />}                          │
│                                                                      │
│  ── Attachments ({count}) ──                                         │
│  {message.attachments.map(a => <AttachmentLink ... />)}              │
│                                                                      │
│  ── Enrichments ──                                                   │
│  <EnrichmentPanel message={message} />                               │
└──────────────────────────────────────────────────────────────────────┘
```

#### 6c. `ParticipantList` (`src/components/messages/ParticipantList.tsx`)

```
Props: { participants: Participant[] }

Renders each participant as:
  <Badge variant="outline">{role}</Badge> {name} ({id})

Roles are color-coded: "from" = blue, "to" = gray, "cc" = muted.
```

#### 6d. `AudioPlayer` (`src/components/messages/AudioPlayer.tsx`)

```
Props: { esIndex: string; docId: string }

Behavior:
1. On mount, call getAudioUrl(esIndex, docId) to get pre-signed S3 URL
2. Render HTML5 <audio> element with controls
3. Show loading spinner while URL is being fetched
4. Handle error (audio not available) gracefully with a fallback message
5. The URL has an expiry — re-fetch if playback fails with 403

Uses: useQuery with queryKey ["audio", esIndex, docId], staleTime set to
the expires_in value returned by the API (minus a safety margin).
```

#### 6e. `EnrichmentPanel` (`src/components/messages/EnrichmentPanel.tsx`)

```
Props: { message: ESMessage }

Layout:
┌──────────────────────────────────────────────────────────────────────┐
│  Sentiment: {message.sentiment}  Score: {sentiment_score}            │
│  Risk Score: {message.risk_score ?? "—"}                             │
│                                                                      │
│  Matched Policies: {matched_policies.join(", ") || "None"}          │
│                                                                      │
│  Entities:                                                           │
│  {entities.map(e => <Badge>{e.label}: {e.text}</Badge>)}            │
└──────────────────────────────────────────────────────────────────────┘

Only render sections that have data. If no enrichments at all, show
"No enrichment data available."
```

#### 6f. `DecisionTimeline` (`src/components/alerts/DecisionTimeline.tsx`)

```
Props: { decisions: DecisionOut[] }

Renders a vertical timeline (newest first):
┌──────────────────────────────────────────────────────────────────────┐
│  ● {status_name}                        {formatRelative(decided_at)} │
│    Reviewer: {reviewer_id}                                           │
│    {comment && <p>{comment}</p>}                                     │
│  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─                                  │
│  ● {status_name}                        {formatRelative(decided_at)} │
│    ...                                                               │
└──────────────────────────────────────────────────────────────────────┘

Empty state: "No decisions yet."
Uses <ScrollArea> if list is long (> 5 entries).
```

#### 6g. `DecisionForm` (`src/components/alerts/DecisionForm.tsx`)

```
Props: { alertId: string; alertStatus: AlertStatus; onSuccess?: () => void }

State:
- selectedStatusId (from decision-statuses)
- comment (text)

Data:
- useDecisionStatuses() — loads dropdown options
- useCreateDecision(alertId) — mutation

Layout:
┌──────────────────────────────────────────────────────────────────────┐
│  Submit Decision                                                     │
│                                                                      │
│  Status:  <Select>                                                   │
│           {statuses.map(s => <Option>{s.name}</Option>)}             │
│           {s.is_terminal && " (closes alert)"}                       │
│                                                                      │
│  Comment: <Textarea placeholder="Add a comment..." />               │
│                                                                      │
│  <Button type="submit" disabled={!selectedStatusId || isPending}>   │
│    Submit Decision                                                   │
│  </Button>                                                           │
└──────────────────────────────────────────────────────────────────────┘

Behavior:
- On submit, call createDecision mutation
- On success: reset form, call onSuccess callback, show success state briefly
- If alert is already "closed", show form disabled with message "Alert is closed"
- Submit button shows loading spinner while mutation is pending
```

#### 6h. `AlertDetailPage` (`src/pages/AlertDetailPage.tsx`)

Orchestrates all alert detail components.

```
Route params: { id } from useParams()

Data:
- useAlert(id) — alert with linked message
- useDecisions(id) — decision history

Layout:
┌──────────────────────────────────────────────────────────────────────┐
│  ← Back to Alerts                                                    │
│                                                                      │
│  <AlertMetadataCard alert={alert} />                                 │
│                                                                      │
│  <Tabs defaultValue="message">                                       │
│    <TabsList>                                                        │
│      <Tab value="message">Message</Tab>                              │
│      <Tab value="decisions">Decisions ({decisions.length})</Tab>     │
│    </TabsList>                                                       │
│                                                                      │
│    <TabsContent value="message">                                     │
│      {alert.message                                                  │
│        ? <MessageDisplay message={alert.message}                     │
│            esIndex={alert.es_index} />                               │
│        : <p>Message not found in Elasticsearch</p>}                  │
│    </TabsContent>                                                    │
│                                                                      │
│    <TabsContent value="decisions">                                   │
│      <DecisionTimeline decisions={decisions} />                      │
│    </TabsContent>                                                    │
│  </Tabs>                                                             │
│                                                                      │
│  ── Submit Decision ──                                               │
│  <DecisionForm alertId={id} alertStatus={alert.status} />            │
└──────────────────────────────────────────────────────────────────────┘

Loading: Full-page skeleton (metadata card skeleton + tabs skeleton)
Error: "Alert not found" with back link
```

---

### Step 7 — Queue Pages (`/queues`, `/queues/:id`)

#### 7a. `MyQueueList` (`src/components/queues/MyQueueList.tsx`)

Shown to reviewers — their assigned batches across all queues.

```
Data: useMyQueue()

Layout:
┌──────────────────────────────────────────────────────────────────────┐
│  My Assigned Batches                                                 │
│                                                                      │
│  {batches.map(b => <BatchCard batch={b} />)}                        │
│                                                                      │
│  Empty: "No batches assigned to you."                                │
└──────────────────────────────────────────────────────────────────────┘
```

#### 7b. `BatchCard` (`src/components/queues/BatchCard.tsx`)

```
Props: { batch: BatchOut }

Layout:
┌──────────────────────────────────────────────────────────────────────┐
│  {batch.name || "Unnamed Batch"}                <StatusBadge>        │
│  Queue: {batch.queue_id}  Items: {batch.item_count}                  │
│  Assigned: {formatRelative(batch.assigned_at)}                       │
│                              [Review Batch →]                        │
└──────────────────────────────────────────────────────────────────────┘

Click "Review Batch" → navigate to /queues/{queue_id}?batch={batch_id}
```

#### 7c. `BatchItemList` (`src/components/queues/BatchItemList.tsx`)

```
Props: { queueId: string; batchId: string }

Data: useBatchItems(queueId, batchId)

Layout:
  Ordered list of alert IDs linked to /alerts/{alert_id}
  Each item shows: position number, alert_id (as link), created_at
  Current item highlighted if navigating sequentially
```

#### 7d. `BatchProgress` (`src/components/queues/BatchProgress.tsx`)

```
Props: { decided: number; total: number }

Renders: progress bar + "X of Y reviewed" text
Uses Tailwind utility classes for the bar (no additional dependency).
```

#### 7e. `QueuesPage` (`src/pages/QueuesPage.tsx`)

Role-aware page:

```
Data:
- useMyQueue() — always loaded for reviewers
- useQueues() — loaded for supervisors

Layout (reviewer):
┌──────────────────────────────────────────────────────────────────────┐
│  <h1>My Queue</h1>                                                   │
│  <MyQueueList />                                                     │
└──────────────────────────────────────────────────────────────────────┘

Layout (supervisor — sees all queues + their own assignments):
┌──────────────────────────────────────────────────────────────────────┐
│  <h1>Review Queues</h1>                                              │
│                                                                      │
│  <Tabs defaultValue="my-queue">                                      │
│    <Tab value="my-queue">My Batches</Tab>                            │
│    <Tab value="all-queues">All Queues</Tab>                          │
│  </Tabs>                                                             │
│                                                                      │
│  TabsContent "my-queue": <MyQueueList />                             │
│  TabsContent "all-queues": queue list table (name, batch_count,      │
│    total_items, created_at) — click row → /queues/{id}               │
└──────────────────────────────────────────────────────────────────────┘
```

#### 7f. `QueueDetailPage` (`src/pages/QueueDetailPage.tsx`)

```
Route params: { id } from useParams()

Data:
- useQueue(id) — queue detail with batch_count, total_items

Layout:
┌──────────────────────────────────────────────────────────────────────┐
│  ← Back to Queues                                                    │
│                                                                      │
│  <h1>{queue.name}</h1>                                               │
│  {queue.description}                                                 │
│  Batches: {queue.batch_count}  Total Items: {queue.total_items}      │
│                                                                      │
│  Note: Full batch management (create, assign, populate) is           │
│  Phase 6 scope. This page shows read-only queue detail for now.      │
└──────────────────────────────────────────────────────────────────────┘
```

---

### Step 8 — Update Routes in App.tsx

Replace `<ComingSoon>` placeholders with actual page components:

```tsx
// Before (Phase 4):
<Route path="/alerts" element={<ComingSoon label="Alerts" />} />
<Route path="/alerts/:id" element={<ComingSoon label="Alert Detail" />} />
<Route path="/queues" element={<ComingSoon label="Queues" />} />

// After (Phase 5):
<Route path="/alerts" element={<AlertsPage />} />
<Route path="/alerts/:id" element={<AlertDetailPage />} />
<Route path="/queues" element={<QueuesPage />} />
<Route path="/queues/:id" element={<QueueDetailPage />} />
```

The remaining placeholders (`/messages`, `/policies`, `/admin`, `/audit`) stay as `<ComingSoon>` for Phase 6.

---

### Step 9 — Add `QueueItemOut` to Types

Add to `src/lib/types.ts`:

```typescript
// ── Queue Items ──────────────────────────────────────

export interface QueueItemOut {
  id: string;
  batch_id: string;
  alert_id: string;
  position: number;
  created_at: string;
}
```

---

### Step 10 — Tests

#### Frontend Tests (Vitest + Testing Library)

| Test File | What it Covers |
|---|---|
| `tests/AlertTable.test.tsx` | Renders table rows, sort toggles, pagination, row click navigation |
| `tests/AlertFilters.test.tsx` | Filter selection updates URL params, clear filters resets |
| `tests/AlertDetailPage.test.tsx` | Renders metadata, message, decisions; form submission flow |
| `tests/DecisionForm.test.tsx` | Status dropdown loads, submit calls mutation, disables when closed |
| `tests/MyQueueList.test.tsx` | Renders batch cards, empty state, links to queue detail |

**Test setup:**
- Mock `apiFetch` at the module level using `vi.mock("@/api/client")`
- Wrap components in `QueryClientProvider` + `MemoryRouter`
- Use `@testing-library/user-event` for interactions
- Use `waitFor` for async state updates

---

## 5. Implementation Order (Recommended)

Work in this order to stay unblocked and allow incremental testing:

| # | Task | Depends On | Est. Complexity |
|---|---|---|---|
| 1 | Install shadcn/ui components | — | Low |
| 2 | Add `QueueItemOut` to `lib/types.ts` | — | Low |
| 3 | API modules (`alerts.ts` extend, `decisions.ts`, `queues.ts`, `messages.ts`) | — | Low |
| 4 | TanStack Query hooks (`useAlerts` extend, `useDecisions`, `useQueues`) | Step 3 | Low |
| 5 | `AlertSeverityBadge` + `AlertStatusBadge` | Step 1 | Low |
| 6 | `AlertFilters` | Step 1, 5 | Medium |
| 7 | `AlertTable` | Step 5, 1 | Medium |
| 8 | `AlertsPage` | Step 4, 6, 7 | Medium |
| 9 | `ParticipantList` | — | Low |
| 10 | `EnrichmentPanel` | — | Low |
| 11 | `AudioPlayer` | Step 3 (messages API) | Medium |
| 12 | `MessageDisplay` | Step 9, 10, 11 | Medium |
| 13 | `DecisionTimeline` | Step 1 | Low |
| 14 | `DecisionForm` | Step 4 (useDecisions) | Medium |
| 15 | `AlertMetadataCard` | Step 5 | Low |
| 16 | `AlertDetailPage` | Step 12, 13, 14, 15 | High |
| 17 | `BatchCard` + `BatchProgress` | — | Low |
| 18 | `MyQueueList` | Step 4, 17 | Low |
| 19 | `BatchItemList` | Step 4 | Low |
| 20 | `QueuesPage` | Step 18 | Medium |
| 21 | `QueueDetailPage` | Step 4, 19 | Low |
| 22 | Update `App.tsx` routes | Step 8, 16, 20, 21 | Low |
| 23 | Write tests | All above | Medium |

---

## 6. Keyboard Shortcuts (Stretch)

If time permits, add keyboard navigation for the alert review workflow:

| Key | Context | Action |
|---|---|---|
| `j` / `k` | Alert table | Move selection down/up |
| `Enter` | Alert table | Open selected alert |
| `Escape` | Alert detail | Back to alert list |
| `n` / `p` | Alert detail (in batch) | Next/previous alert in batch |

Implementation: a `useHotkeys` hook (or `react-hotkeys-hook` library) bound at the page level. This is optional for Phase 5 and can be deferred.

---

## 7. Files Summary

### New Files (17)

```
src/api/decisions.ts
src/api/queues.ts
src/api/messages.ts
src/hooks/useDecisions.ts
src/hooks/useQueues.ts
src/pages/AlertsPage.tsx
src/pages/AlertDetailPage.tsx
src/pages/QueuesPage.tsx
src/pages/QueueDetailPage.tsx
src/components/alerts/AlertTable.tsx
src/components/alerts/AlertFilters.tsx
src/components/alerts/AlertSeverityBadge.tsx
src/components/alerts/AlertStatusBadge.tsx
src/components/alerts/AlertMetadataCard.tsx
src/components/alerts/DecisionForm.tsx
src/components/alerts/DecisionTimeline.tsx
src/components/messages/MessageDisplay.tsx
src/components/messages/ParticipantList.tsx
src/components/messages/AudioPlayer.tsx
src/components/messages/EnrichmentPanel.tsx
src/components/queues/MyQueueList.tsx
src/components/queues/BatchCard.tsx
src/components/queues/BatchItemList.tsx
src/components/queues/BatchProgress.tsx
```

### Modified Files (4)

```
src/api/alerts.ts        — add getAlerts, getAlert, updateAlertStatus
src/hooks/useAlerts.ts   — add useAlerts, useAlert, useUpdateAlertStatus
src/lib/types.ts         — add QueueItemOut
src/App.tsx              — replace ComingSoon with real pages, add /queues/:id route
```

### New shadcn/ui Components (~9)

```
src/components/ui/table.tsx
src/components/ui/pagination.tsx
src/components/ui/textarea.tsx
src/components/ui/tabs.tsx
src/components/ui/skeleton.tsx
src/components/ui/popover.tsx
src/components/ui/calendar.tsx
src/components/ui/command.tsx
src/components/ui/scroll-area.tsx
```

---

## 8. Acceptance Criteria

Phase 5 is complete when:

1. **Alerts page** loads at `/alerts`, displays paginated alerts from the backend, supports filtering by severity and status, and navigates to detail on row click
2. **Alert detail page** loads at `/alerts/:id`, shows alert metadata, the linked ES message (body, participants, enrichments), decision history, and a working decision submission form
3. **Decision submission** creates a decision via `POST /alerts/{id}/decisions`, refreshes the decision history and alert status, and auto-closes the alert when a terminal status is chosen
4. **Queues page** loads at `/queues`, shows the current reviewer's assigned batches (via `GET /my-queue`), and links to alert details for each batch item
5. **Queue detail page** loads at `/queues/:id`, shows queue metadata and batch information
6. **All pages** handle loading states (skeletons), error states (error cards with retry), and empty states gracefully
7. **Route guards** enforce role-based access — reviewers see their queue, supervisors see all queues
8. **URL-synced filters** on the alerts page allow sharing filtered views via URL
9. **No regressions** — dashboard, login, and existing components continue to work
10. **Frontend builds** without TypeScript errors (`npm run build` succeeds)
