# Phase 2 — Agent Builder UI + Natural Language Search

## Context

Phase 1a (database + runtime skeleton + NL search backend) and Phase 1b (executor, tools, CRUD API) are complete. The backend provides full REST APIs for agent CRUD, execution, model management, and tool listing. The frontend has zero agent-related code. This plan implements the Phase 2 deliverables: a full Agent Builder UI and natural language search on the Messages page.

---

## 1. TypeScript Types (`lib/types.ts`)

Add agent-related types at the end of the existing types file.

**Types to add:**
- `AgentStatus` — `"active" | "inactive"`
- `RunStatus` — `"pending" | "running" | "completed" | "failed" | "cancelled"`
- `DataSourceConfig` — `{ source_type: "elasticsearch" | "postgresql"; source_identifier: string }`
- `ToolSummary` — `{ id, name, display_name, tool_config }`
- `ModelOut` — `{ id, name, provider, model_id, base_url, max_tokens, is_active, created_by, created_at, updated_at }`
- `AgentOut` — `{ id, name, description, model: ModelOut, system_prompt, temperature, max_iterations, output_schema, tools: ToolSummary[], data_sources: DataSourceConfig[], is_builtin, is_active, created_by, created_at, updated_at }`
- `ToolOut` — `{ id, name, display_name, description, category, parameters_schema, is_active, created_at }`
- `RunStepOut` — `{ id, step_order, step_type, tool_name, input, output, token_usage, duration_ms, created_at }`
- `RunOut` — `{ id, agent_id, status: RunStatus, input, output, error_message, token_usage, iterations, duration_ms, triggered_by, created_at, completed_at, steps?: RunStepOut[] }`
- `NLSearchResponse` — extends `MessageSearchResponse` with `generated_query: Record<string, unknown>; explanation: string`

**File:** `ui/frontend/src/lib/types.ts`

---

## 2. API Client (`api/agents.ts`)

New file. Uses `apiFetch` from `./client` (same pattern as `api/entities.ts`).

**Functions:**

```
// Agents
getAgents(params: { offset, limit, filter? }) → PaginatedResponse<AgentOut>
getAgent(id: string) → AgentOut
createAgent(body: AgentCreateBody) → AgentOut
updateAgent(id: string, body: AgentUpdateBody) → AgentOut
deleteAgent(id: string) → void
cloneAgent(id: string) → AgentOut

// Models
getAgentModels() → ModelOut[]

// Tools
getAgentTools() → ToolOut[]

// Runs
executeAgent(body: { agent_id, input }) → RunOut
getAgentRuns(params: { agent_id?, offset, limit }) → PaginatedResponse<RunOut>
getAgentRun(id: string) → RunOut
```

**Interfaces (request bodies):**
- `AgentCreateBody` — `{ name, description?, model_id, system_prompt, temperature, max_iterations, output_schema?, tool_ids, tool_configs?, data_sources }`
- `AgentUpdateBody` — all fields optional

**File:** `ui/frontend/src/api/agents.ts`

---

## 3. API Client for NL Search (`api/messages.ts`)

Add to existing file:

```typescript
export async function nlSearchMessages(body: { query: string; offset?: number; limit?: number }): Promise<NLSearchResponse> {
  return apiFetch("/messages/nl-search", { method: "POST", body: JSON.stringify(body) });
}
```

**File:** `ui/frontend/src/api/messages.ts`

---

## 4. React Query Hooks (`hooks/useAgents.ts`)

New file. Follows patterns from `hooks/useEntities.ts`.

**Query hooks:**
- `useAgents(params)` — queryKey `["agents", "list", params]`
- `useAgent(id)` — queryKey `["agents", id]`, `enabled: !!id`
- `useAgentModels()` — queryKey `["agent-models"]`
- `useAgentTools()` — queryKey `["agent-tools"]`
- `useAgentRuns(params)` — queryKey `["agent-runs", "list", params]`
- `useAgentRun(id)` — queryKey `["agent-runs", id]`, `enabled: !!id`

**Mutation hooks:**
- `useCreateAgent()` — invalidates `["agents", "list"]` on success
- `useUpdateAgent()` — invalidates `["agents", "list"]` and `["agents", id]`
- `useDeleteAgent()` — invalidates `["agents", "list"]`
- `useCloneAgent()` — invalidates `["agents", "list"]`
- `useExecuteAgent()` — invalidates `["agent-runs", "list"]`

**File:** `ui/frontend/src/hooks/useAgents.ts`

---

## 5. React Query Hook for NL Search (`hooks/useMessages.ts`)

Add to existing file:

```typescript
export function useNLSearch(query: string, offset: number, limit: number) {
  return useQuery({
    queryKey: ["messages", "nl-search", query, offset, limit],
    queryFn: () => nlSearchMessages({ query, offset, limit }),
    enabled: !!query,
  });
}
```

**File:** `ui/frontend/src/hooks/useMessages.ts`

---

## 6. Agents List Page (`pages/AgentsPage.tsx`)

New file. Follows `EntitiesPage.tsx` pattern.

**Layout:**
- Header: "Agents" title + "New Agent" button (supervisor+ role)
- Filter tabs: All / My Agents / Built-in (using `Tabs` component from `ui/tabs`)
- Agent table with columns: Name, Model (name), Tools (count), Status (badge), Last Run (relative time), Created By
- Pagination at bottom
- Row click navigates to `/agents/:id`
- URL search params: `?tab=all|mine|builtin&offset=0`

**Components used:** `Tabs`, `Button`, `Badge`, `Table`, `Pagination`, `Skeleton`

**File:** `ui/frontend/src/pages/AgentsPage.tsx`

---

## 7. Agent Detail Page (`pages/AgentDetailPage.tsx`)

New file. Follows `EntityDetailPage.tsx` pattern.

**Layout:**
- Header: Agent name, status badge (active/inactive), builtin badge
- Metadata row: Model, Temperature, Max Iterations, Created At
- Action buttons: Edit (supervisor+), Clone (supervisor+), Deactivate (admin), Delete (admin)
- **Configuration Card:** System prompt (scrollable), output schema (if set, as JSON)
- **Tools Card:** List of assigned tools with descriptions
- **Data Sources Card:** List of ES indices and PG schemas
- **Run History Card:** Table of recent runs (status badge, input snippet, duration, tokens, created_at), click to expand steps
  - Inline `RunStepInspector` — expandable accordion showing each step's type, tool name, input/output JSON

**File:** `ui/frontend/src/pages/AgentDetailPage.tsx`

---

## 8. Agent Editor Page (`pages/AgentEditorPage.tsx`)

New file. Multi-step wizard following `GenerateAlertsDialog.tsx` step-machine pattern, but rendered as a full page (not a dialog).

**Route:** `/agents/new` (create) and `/agents/:id/edit` (edit — pre-fills from existing agent)

**Steps:**

### Step 1 — Identity
- Name (text input, required)
- Description (textarea, optional)

### Step 2 — Model & Behavior
- Model (Select dropdown, populated from `useAgentModels()`)
- Temperature (range input / slider, 0.0–1.0, step 0.1)
- Max Iterations (number input, 1–50)

### Step 3 — Instructions
- System Prompt (large Textarea, ~10 rows)

### Step 4 — Tools & Data Sources
- **Tools section:** Checkboxes for each tool from `useAgentTools()`, showing `display_name` and `description`
- **Data Sources section:** Dynamic list of `{ source_type (select: ES/PG), source_identifier (text input) }` with Add/Remove buttons

### Step 5 — Output Schema (Optional)
- Toggle: Free-form text vs. Structured JSON
- If structured: Textarea for JSON Schema (with basic JSON validation)

### Step 6 — Review & Save
- Summary of all configured fields in a read-only Card layout
- "Save" button (calls `createAgent` or `updateAgent` mutation)
- On success: toast + navigate to `/agents/:id`

**State management:** Single `useState` object holding all wizard state. Step navigation via `step` state variable. Back/Next buttons.

**File:** `ui/frontend/src/pages/AgentEditorPage.tsx`

---

## 9. Agent Components (`components/agents/`)

### `AgentTable.tsx`
Table component for the agents list. Props: `{ data, total, offset, limit, onPageChange, isLoading }`. Follows `EntityTable.tsx` pattern.

### `RunHistory.tsx`
Table of agent runs with status badges. Props: `{ agentId }`. Uses `useAgentRuns` internally. Expandable rows showing run steps via `Accordion`.

### `RunStepInspector.tsx`
Accordion showing step details for a single run. Props: `{ steps: RunStepOut[] }`. Shows step_type badge, tool_name, and collapsible input/output JSON.

**Directory:** `ui/frontend/src/components/agents/`

---

## 10. Natural Language Search on Messages Page

### `SearchModeToggle.tsx`
Simple tab toggle between "Keyword" and "Natural Language" modes. Uses `Tabs` component. Props: `{ mode, onChange }`.

**File:** `ui/frontend/src/components/messages/SearchModeToggle.tsx`

### `NLQueryExplainer.tsx`
Info banner showing the LLM's explanation + collapsible "View generated query" section with formatted JSON. Props: `{ explanation, generatedQuery }`.

**File:** `ui/frontend/src/components/messages/NLQueryExplainer.tsx`

### `MessagesPage.tsx` updates
- Add `mode` state (`"keyword" | "nl"`) synced to URL param `?mode=nl`
- Render `SearchModeToggle` above the search form
- When `mode === "keyword"`: current behavior (unchanged)
- When `mode === "nl"`:
  - Show single textarea input with placeholder "Ask a question, e.g. 'Show me emails about the Q3 report from last month'"
  - Hide filter panel
  - Call `useNLSearch` instead of `useMessageSearch`
  - Show `NLQueryExplainer` above results
  - Reuse same `MessageSearchResults` component for hits

**File:** `ui/frontend/src/pages/MessagesPage.tsx`

---

## 11. Navigation Update (`Sidebar.tsx`)

Add "Agents" nav item to `NAV_ITEMS` array, after Entities:

```typescript
{ to: "/agents", label: "Agents", icon: Bot, minRole: "reviewer" },
```

Import `Bot` from `lucide-react`.

**File:** `ui/frontend/src/components/layout/Sidebar.tsx`

---

## 12. Routing (`App.tsx`)

Add agent routes inside the authenticated `AppShell` Route:

```typescript
<Route path="/agents" element={<AgentsPage />} />
<Route path="/agents/new" element={<AgentEditorPage />} />
<Route path="/agents/:id" element={<AgentDetailPage />} />
<Route path="/agents/:id/edit" element={<AgentEditorPage />} />
```

**File:** `ui/frontend/src/App.tsx`

---

## Implementation Order

1. Types in `lib/types.ts`
2. API client `api/agents.ts` + NL search addition to `api/messages.ts`
3. Hooks `hooks/useAgents.ts` + NL search hook in `hooks/useMessages.ts`
4. Sidebar nav update + App.tsx routing
5. `AgentsPage` + `AgentTable`
6. `AgentDetailPage` + `RunHistory` + `RunStepInspector`
7. `AgentEditorPage` (create + edit)
8. NL Search: `SearchModeToggle` + `NLQueryExplainer` + `MessagesPage` updates

---

## Files to Create (10 new)

| # | File |
|---|---|
| 1 | `ui/frontend/src/api/agents.ts` |
| 2 | `ui/frontend/src/hooks/useAgents.ts` |
| 3 | `ui/frontend/src/pages/AgentsPage.tsx` |
| 4 | `ui/frontend/src/pages/AgentDetailPage.tsx` |
| 5 | `ui/frontend/src/pages/AgentEditorPage.tsx` |
| 6 | `ui/frontend/src/components/agents/AgentTable.tsx` |
| 7 | `ui/frontend/src/components/agents/RunHistory.tsx` |
| 8 | `ui/frontend/src/components/agents/RunStepInspector.tsx` |
| 9 | `ui/frontend/src/components/messages/SearchModeToggle.tsx` |
| 10 | `ui/frontend/src/components/messages/NLQueryExplainer.tsx` |

## Files to Modify (5)

| # | File | Change |
|---|---|---|
| 1 | `ui/frontend/src/lib/types.ts` | Add agent/run/NL search types |
| 2 | `ui/frontend/src/api/messages.ts` | Add `nlSearchMessages()` |
| 3 | `ui/frontend/src/hooks/useMessages.ts` | Add `useNLSearch()` |
| 4 | `ui/frontend/src/pages/MessagesPage.tsx` | Add NL search mode toggle and handling |
| 5 | `ui/frontend/src/components/layout/Sidebar.tsx` | Add Agents nav item |
| 6 | `ui/frontend/src/App.tsx` | Add agent routes |

## Key Patterns to Follow

- **API client:** `apiFetch` from `api/client.ts`, URLSearchParams for GET params
- **Hooks:** React Query with `["resource", "list", params]` query keys, `void qc.invalidateQueries()` on mutations
- **Pages:** URL search params for filters/pagination, `useAuthStore` for role checks
- **Tables:** Skeleton loading states, row click navigation, Badge for status
- **Forms:** `useState` for form state, toast notifications on success/error
- **Wizard:** Step machine pattern from `GenerateAlertsDialog.tsx`
- **Icons:** `lucide-react`, used as `<IconName className="h-4 w-4" />`
- **Styling:** Tailwind utility classes, `cn()` for conditional classes
- **Roles:** `hasRole(user.roles, "supervisor")` for access checks

## Verification

1. `npm run build` — TypeScript compilation succeeds
2. Navigate to `/agents` — list page loads, shows empty state or agents
3. Click "New Agent" — editor wizard renders all 6 steps
4. Create an agent — appears in list, detail page shows config
5. Navigate to `/agents/:id` — detail page shows tools, data sources, run history
6. Edit an agent — pre-fills form, saves changes
7. Navigate to `/messages` — search mode toggle appears
8. Switch to NL mode — textarea input, search calls NL endpoint, explanation displays
