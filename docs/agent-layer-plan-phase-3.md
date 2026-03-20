# Phase 3 — Playground & Streaming: Detailed Implementation Plan

**Goal:** Interactive agent testing with real-time output. Users can execute agents from a chat-like playground interface and watch tool calls, LLM reasoning, and results appear in real time via Server-Sent Events (SSE).

**Prerequisites:** Phases 1a, 1b, and 2 are complete. Agent CRUD, execution, tools, and the Agent Builder UI are functional.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [SSE Event Protocol](#2-sse-event-protocol)
3. [Agent Runtime — Streaming Execution](#3-agent-runtime--streaming-execution)
4. [UI Backend — SSE Proxy](#4-ui-backend--sse-proxy)
5. [Frontend — Playground Page](#5-frontend--playground-page)
6. [Run Cancellation](#6-run-cancellation)
7. [File Inventory](#7-file-inventory)
8. [Implementation Steps](#8-implementation-steps)
9. [Testing Strategy](#9-testing-strategy)

---

## 1. Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  FRONTEND — AgentPlaygroundPage                                              │
│                                                                              │
│  1. POST /api/v1/agent-runs/stream                                          │
│     → returns run_id immediately                                            │
│  2. GET  /api/v1/agent-runs/{run_id}/stream                                 │
│     → SSE connection: receives step events in real time                     │
│                                                                              │
│  EventSource ←──SSE──┐                                                      │
└──────────────────────┼──────────────────────────────────────────────────────┘
                       │
┌──────────────────────┼──────────────────────────────────────────────────────┐
│  UI BACKEND          │                                                      │
│                      │                                                      │
│  POST /api/v1/agent-runs/stream                                             │
│    → proxy to runtime POST /execute-stream → returns {run_id}              │
│                                                                              │
│  GET /api/v1/agent-runs/{run_id}/stream                                     │
│    → proxy SSE from runtime GET /runs/{run_id}/stream                      │
└──────────────────────┬──────────────────────────────────────────────────────┘
                       │
┌──────────────────────┼──────────────────────────────────────────────────────┐
│  AGENT RUNTIME       │                                                      │
│                      │                                                      │
│  POST /execute-stream                                                       │
│    → creates Run, starts execution in background task, returns {run_id}     │
│                                                                              │
│  GET /runs/{run_id}/stream                                                  │
│    → SSE endpoint: streams step events from asyncio.Queue until done       │
│                                                                              │
│  StreamingAuditCallback writes steps to DB AND pushes to in-memory queue   │
│                                                                              │
│  POST /runs/{run_id}/cancel                                                 │
│    → sets cancellation flag, agent stops at next iteration                  │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Key design decisions:**

- **Two-request pattern**: The frontend sends a POST to start execution (returns `run_id` immediately), then opens an SSE connection on `GET /runs/{run_id}/stream` to receive events. This avoids long-lived POST requests and is compatible with load balancers, proxies, and browser reconnection.
- **In-memory event queue**: The `StreamingAuditCallback` pushes events to an `asyncio.Queue` keyed by `run_id`. The SSE endpoint reads from this queue. This keeps the streaming path simple and avoids polling the database.
- **Run registry**: A `RunRegistry` singleton maps `run_id → { task, queue, cancelled }`. It manages background tasks and provides the queue for SSE consumers.
- **Graceful degradation**: If the SSE connection drops, the frontend can reconnect and the `GET /runs/{run_id}/stream` endpoint replays events from the database (steps already committed) before switching to live queue events.

---

## 2. SSE Event Protocol

Each SSE event has a `event:` type and `data:` JSON payload.

### Event Types

| Event | When Sent | Payload |
|---|---|---|
| `run_started` | Run created, execution begins | `{ run_id, agent_id, status: "running" }` |
| `llm_start` | LLM call begins | `{ step_order, type: "llm_call" }` |
| `llm_end` | LLM call completes | `{ step_order, type: "llm_call", output, token_usage, duration_ms }` |
| `tool_start` | Tool invocation begins | `{ step_order, type: "tool_call", tool_name, input }` |
| `tool_end` | Tool returns result | `{ step_order, type: "tool_result", tool_name, output, duration_ms }` |
| `tool_error` | Tool raises exception | `{ step_order, type: "tool_error", tool_name, error, duration_ms }` |
| `run_completed` | Run finishes successfully | `{ run_id, status: "completed", output, iterations, duration_ms, token_usage }` |
| `run_failed` | Run fails with error | `{ run_id, status: "failed", error_message, iterations, duration_ms }` |
| `run_cancelled` | Run was cancelled | `{ run_id, status: "cancelled", iterations, duration_ms }` |
| `heartbeat` | Every 15s while running | `{}` |

### Example SSE Stream

```
event: run_started
data: {"run_id": "abc-123", "agent_id": "def-456", "status": "running"}

event: llm_start
data: {"step_order": 1, "type": "llm_call"}

event: llm_end
data: {"step_order": 1, "type": "llm_call", "output": {"response": "I'll search for..."}, "token_usage": {"prompt_tokens": 150, "completion_tokens": 42}, "duration_ms": 1200}

event: tool_start
data: {"step_order": 2, "type": "tool_call", "tool_name": "es_search", "input": {"query": "quarterly earnings", "index": "messages-*"}}

event: tool_end
data: {"step_order": 2, "type": "tool_result", "tool_name": "es_search", "output": {"hits": 12, "results": [...]}, "duration_ms": 340}

event: llm_start
data: {"step_order": 3, "type": "llm_call"}

event: llm_end
data: {"step_order": 3, "type": "llm_call", "output": {"response": "Based on my analysis..."}, "token_usage": {"prompt_tokens": 890, "completion_tokens": 256}, "duration_ms": 3100}

event: run_completed
data: {"run_id": "abc-123", "status": "completed", "output": {"response": "Based on my analysis..."}, "iterations": 3, "duration_ms": 4640, "token_usage": {"prompt_tokens": 1040, "completion_tokens": 298, "total_tokens": 1338}}

```

---

## 3. Agent Runtime — Streaming Execution

### 3.1 Run Registry (`agents/umbrella_agents/run_registry.py`)

Manages in-flight runs with their event queues and background tasks.

```python
@dataclass
class ManagedRun:
    run_id: uuid.UUID
    queue: asyncio.Queue          # SSE events pushed here
    task: asyncio.Task             # background execution task
    cancelled: asyncio.Event       # set to request cancellation

class RunRegistry:
    """Singleton registry for in-flight agent runs."""
    _runs: dict[uuid.UUID, ManagedRun]

    def register(run_id, task, queue) -> ManagedRun
    def get(run_id) -> ManagedRun | None
    def cancel(run_id) -> bool
    def remove(run_id) -> None
    @property
    def active_count(self) -> int
```

**Lifecycle:**
1. `POST /execute-stream` creates a `ManagedRun` and starts the execution as a background `asyncio.Task`.
2. The `StreamingAuditCallback` pushes events to the `ManagedRun.queue`.
3. `GET /runs/{run_id}/stream` reads from the queue and yields SSE events.
4. On completion/failure/cancellation, a terminal event is pushed and the run is cleaned up after a grace period (60s, to allow late-connecting SSE clients).

### 3.2 Streaming Audit Callback (`agents/umbrella_agents/callbacks/streaming.py`)

Extends the existing `AuditCallbackHandler` pattern. Writes steps to the database (for persistence) AND pushes events to an `asyncio.Queue` (for live streaming).

```python
class StreamingAuditCallback(AsyncCallbackHandler):
    """Records run steps to DB and pushes SSE events to a queue."""

    def __init__(self, run_id, session_factory, event_queue):
        self.run_id = run_id
        self.session_factory = session_factory
        self.event_queue = event_queue    # asyncio.Queue
        self._step_counter = 0
        self._timers = {}

    async def _write_step(self, step_type, input_data, ...):
        # 1. Write to DB (same as existing AuditCallbackHandler)
        # 2. Push event dict to self.event_queue

    async def on_llm_start(self, ...):
        # Push llm_start event to queue
        # Start timer

    async def on_llm_end(self, ...):
        # Write step to DB
        # Push llm_end event with output, token_usage, duration

    async def on_tool_start(self, ...):
        # Write tool_call step to DB
        # Push tool_start event

    async def on_tool_end(self, ...):
        # Write tool_result step to DB
        # Push tool_end event

    async def on_tool_error(self, ...):
        # Write tool_error step to DB
        # Push tool_error event
```

### 3.3 Streaming Executor (`executor.py` modifications)

Add a new function `execute_agent_streaming()` alongside the existing `execute_agent()`. The existing non-streaming function remains unchanged for backward compatibility.

```python
async def execute_agent_streaming(
    agent_id: uuid.UUID,
    user_input: str,
    triggered_by: uuid.UUID,
    session_factory: async_sessionmaker,
    es_client: AsyncElasticsearch,
    event_queue: asyncio.Queue,
    cancelled: asyncio.Event,
    timeout: int = 120,
) -> None:
    """Execute an agent with streaming events pushed to event_queue.

    This is designed to run as a background asyncio.Task.
    Pushes a terminal event (run_completed/run_failed/run_cancelled) at the end.
    """
    # 1. Load agent config (same as execute_agent)
    # 2. Create Run record (status=running)
    # 3. Push run_started event to queue
    # 4. Build tools, LLM, LangGraph agent (same as execute_agent)
    # 5. Use StreamingAuditCallback instead of AuditCallbackHandler
    # 6. Execute with cancellation check:
    #    - Wrap graph.ainvoke() in asyncio.wait with cancelled event
    #    - If cancelled, update run status to "cancelled", push run_cancelled
    # 7. On success: push run_completed
    # 8. On error: push run_failed
    # 9. Push sentinel None to queue to signal stream end
```

**Cancellation mechanism:**
- The `cancelled` event is checked between agent iterations by injecting a custom LangGraph `should_continue` check. When the event is set, the agent stops at the next iteration boundary.
- For immediate responsiveness, the executor also wraps `graph.ainvoke()` with `asyncio.shield` and checks the cancelled flag on each callback invocation.

### 3.4 New Runtime Endpoints

#### `POST /execute-stream` (`agents/umbrella_agents/routers/execute.py`)

Starts an agent execution in the background and returns the `run_id` immediately.

```python
class ExecuteStreamRequest(BaseModel):
    agent_id: uuid.UUID
    input: str
    triggered_by: uuid.UUID

class ExecuteStreamResponse(BaseModel):
    run_id: str
    status: str  # always "running"

@router.post("/execute-stream", response_model=ExecuteStreamResponse)
async def execute_stream(body: ExecuteStreamRequest, request: Request):
    registry: RunRegistry = request.app.state.run_registry
    # Check concurrency limit
    if registry.active_count >= settings.max_concurrent_runs:
        raise HTTPException(429, "Too many concurrent runs")

    # Create queue, cancelled event, background task
    queue = asyncio.Queue(maxsize=100)
    cancelled = asyncio.Event()
    run_id = uuid.uuid4()

    task = asyncio.create_task(
        execute_agent_streaming(
            agent_id=body.agent_id,
            user_input=body.input,
            triggered_by=body.triggered_by,
            session_factory=db.session_factory,
            es_client=es.client,
            event_queue=queue,
            cancelled=cancelled,
        )
    )
    registry.register(run_id, task, queue, cancelled)
    return ExecuteStreamResponse(run_id=str(run_id), status="running")
```

Note: The `run_id` used here is generated by the runtime in `execute_agent_streaming` when it creates the Run DB record, not by the endpoint. The endpoint will need to receive the actual `run_id` from the first queue event or pass it into the function. The cleanest approach: pass a pre-generated `run_id` into `execute_agent_streaming()` so the endpoint knows it immediately.

#### `GET /runs/{run_id}/stream` (`agents/umbrella_agents/routers/stream.py`)

SSE endpoint that streams events from the run's queue.

```python
@router.get("/runs/{run_id}/stream")
async def stream_run(run_id: uuid.UUID, request: Request):
    registry: RunRegistry = request.app.state.run_registry
    managed = registry.get(run_id)

    if managed is None:
        # Run not in memory — check DB for completed run
        # If found, return steps as SSE events from DB (replay)
        # If not found, 404
        ...

    async def event_generator():
        heartbeat_interval = 15  # seconds
        while True:
            try:
                event = await asyncio.wait_for(
                    managed.queue.get(), timeout=heartbeat_interval
                )
                if event is None:
                    break  # sentinel — stream done
                yield {
                    "event": event["event"],
                    "data": json.dumps(event["data"]),
                }
            except asyncio.TimeoutError:
                yield {"event": "heartbeat", "data": "{}"}

    return EventSourceResponse(event_generator())
```

Uses `sse-starlette` (`EventSourceResponse`) for standards-compliant SSE. Add `sse-starlette` to `agents/pyproject.toml` dependencies.

#### `POST /runs/{run_id}/cancel` (`agents/umbrella_agents/routers/stream.py`)

```python
@router.post("/runs/{run_id}/cancel")
async def cancel_run(run_id: uuid.UUID, request: Request):
    registry: RunRegistry = request.app.state.run_registry
    if not registry.cancel(run_id):
        raise HTTPException(404, "Run not found or already completed")
    return {"status": "cancelling"}
```

### 3.5 App Startup Changes (`agents/umbrella_agents/app.py`)

- Create `RunRegistry` singleton and attach to `app.state.run_registry` during lifespan startup.
- On shutdown, cancel all in-flight runs.
- Register new routers: `stream.py`.

---

## 4. UI Backend — SSE Proxy

### 4.1 New Streaming Endpoints (`ui/backend/umbrella_ui/routers/agent_runs.py`)

Add two new endpoints to the existing `agent_runs.py` router.

#### `POST /api/v1/agent-runs/stream`

Starts a streaming execution by proxying to the runtime's `POST /execute-stream`.

```python
@router.post("/stream", status_code=status.HTTP_201_CREATED)
async def execute_agent_stream(
    body: RunCreate,
    settings: Settings,
    current_user: dict,
):
    """Start a streaming agent execution. Returns run_id immediately."""
    url = f"{settings.agents_base_url}/execute-stream"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(url, json={
            "agent_id": str(body.agent_id),
            "input": body.input,
            "triggered_by": str(current_user["id"]),
        })
        resp.raise_for_status()
    return resp.json()  # { run_id, status: "running" }
```

#### `GET /api/v1/agent-runs/{run_id}/stream`

Proxies the SSE stream from the runtime to the frontend. Uses `httpx` streaming to forward events without buffering.

```python
from starlette.responses import StreamingResponse

@router.get("/{run_id}/stream")
async def stream_run(
    run_id: uuid.UUID,
    settings: Settings,
    current_user: dict,
):
    """Proxy SSE stream from agent runtime."""
    url = f"{settings.agents_base_url}/runs/{run_id}/stream"

    async def proxy_stream():
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("GET", url) as resp:
                async for chunk in resp.aiter_text():
                    yield chunk

    return StreamingResponse(
        proxy_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # disable nginx buffering
        },
    )
```

#### `POST /api/v1/agent-runs/{run_id}/cancel`

Proxies cancellation to the runtime.

```python
@router.post("/{run_id}/cancel")
async def cancel_run(
    run_id: uuid.UUID,
    settings: Settings,
    current_user: dict,  # require supervisor role
):
    url = f"{settings.agents_base_url}/runs/{run_id}/cancel"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(url)
        resp.raise_for_status()
    return resp.json()
```

---

## 5. Frontend — Playground Page

### 5.1 New Route

Add to `App.tsx`:

```tsx
<Route path="/agents/:id/playground" element={<AgentPlaygroundPage />} />
```

### 5.2 Page Component (`ui/frontend/src/pages/AgentPlaygroundPage.tsx`)

The playground page has three zones:
1. **Header** — agent name, config link, history link
2. **Output area** — scrollable area showing the agent's response and step trace
3. **Input area** — textarea with send button, pinned to the bottom

```
┌──────────────────────────────────────────────────────────────────────┐
│  Agent: Comms Reviewer                       [Config] [Run History] │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌ Previous Run ─────────────────────────────────────────────────┐  │
│  │  Input: "Review flagged messages from last week"              │  │
│  │  ▸ Step 1: es_search (340ms)                                  │  │
│  │  ▸ Step 2: entity_lookup (120ms)                              │  │
│  │  Output: "Based on my analysis, I found 3 potential..."       │  │
│  │  ── 4.2s │ 1,338 tokens ──────────────────────────────────── │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌ Current Run (streaming) ──────────────────────────────────────┐  │
│  │  Input: "Find unusual trading patterns for entity ABC"        │  │
│  │                                                                │  │
│  │  ● LLM thinking...                          ← spinner         │  │
│  │  ✓ Step 1: es_search("unusual trading" index:messages-*)      │  │
│  │    → 12 hits (340ms)                                          │  │
│  │  ● Step 2: es_aggregation(...)               ← spinner         │  │
│  │                                                                │  │
│  │                                       [Cancel]                │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Ask the agent something...                          [Send]  │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  Model: GPT-4o │ Temperature: 0.0 │ Max iterations: 10              │
└──────────────────────────────────────────────────────────────────────┘
```

**State management:**

```typescript
interface PlaygroundState {
  runs: PlaygroundRun[];        // history of runs in this session
  currentRunId: string | null;  // active streaming run
  isStreaming: boolean;
  input: string;
}

interface PlaygroundRun {
  runId: string;
  input: string;
  status: "running" | "completed" | "failed" | "cancelled";
  steps: StreamStep[];
  output: string | null;
  errorMessage: string | null;
  totalTokens: number | null;
  durationMs: number | null;
}

interface StreamStep {
  stepOrder: number;
  type: "llm_call" | "tool_call" | "tool_result" | "tool_error";
  toolName: string | null;
  input: Record<string, unknown> | null;
  output: Record<string, unknown> | null;
  tokenUsage: Record<string, number> | null;
  durationMs: number | null;
  status: "running" | "done";     // "running" while waiting for _end event
}
```

### 5.3 SSE Hook (`ui/frontend/src/hooks/useAgentStream.ts`)

Custom hook that manages the EventSource lifecycle.

```typescript
export function useAgentStream(agentId: string) {
  // State
  const [runs, setRuns] = useState<PlaygroundRun[]>([]);
  const [currentRunId, setCurrentRunId] = useState<string | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);

  // Start a new run
  const startRun = async (input: string) => {
    // 1. POST /api/v1/agent-runs/stream → { run_id }
    // 2. Create new PlaygroundRun in state
    // 3. Open EventSource on GET /api/v1/agent-runs/{run_id}/stream
    // 4. Wire up event handlers for each SSE event type
  };

  // Cancel current run
  const cancelRun = async () => {
    // POST /api/v1/agent-runs/{currentRunId}/cancel
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      eventSourceRef.current?.close();
    };
  }, []);

  return { runs, currentRunId, isStreaming, startRun, cancelRun };
}
```

**EventSource event handlers:**

```typescript
const es = new EventSource(`/api/v1/agent-runs/${runId}/stream`);

es.addEventListener("run_started", (e) => {
  // Set run status to "running"
});

es.addEventListener("llm_start", (e) => {
  const data = JSON.parse(e.data);
  // Add step with status "running" to current run
});

es.addEventListener("llm_end", (e) => {
  const data = JSON.parse(e.data);
  // Update step: status → "done", add output, token_usage, duration
});

es.addEventListener("tool_start", (e) => {
  const data = JSON.parse(e.data);
  // Add step with status "running", show tool_name and input
});

es.addEventListener("tool_end", (e) => {
  const data = JSON.parse(e.data);
  // Update step: status → "done", add output, duration
});

es.addEventListener("tool_error", (e) => {
  const data = JSON.parse(e.data);
  // Update step: status → "done", add error
});

es.addEventListener("run_completed", (e) => {
  const data = JSON.parse(e.data);
  // Set run status, output, total metrics
  // Close EventSource
});

es.addEventListener("run_failed", (e) => { /* similar */ });
es.addEventListener("run_cancelled", (e) => { /* similar */ });
```

### 5.4 API Functions (`ui/frontend/src/api/agents.ts`)

Add three new functions to the existing agents API module:

```typescript
export async function executeAgentStream(body: {
  agent_id: string;
  input: string;
}): Promise<{ run_id: string; status: string }> {
  return apiFetch("/agent-runs/stream", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function agentRunStreamUrl(runId: string): string {
  return `${API_BASE}/agent-runs/${runId}/stream`;
}

export async function cancelAgentRun(runId: string): Promise<void> {
  return apiFetch(`/agent-runs/${runId}/cancel`, { method: "POST" });
}
```

### 5.5 Playground Components

#### `AgentPlayground.tsx` (`ui/frontend/src/components/agents/AgentPlayground.tsx`)

The main playground container. Manages the `useAgentStream` hook and renders the run list + input area.

```
Props: { agent: AgentOut }

Renders:
- ScrollArea containing PlaygroundRun cards
- Each PlaygroundRun renders:
  - Input prompt (quoted)
  - Steps list (LiveStepTrace component)
  - Final output (when complete)
  - Metadata bar (tokens, duration)
- Input area at bottom:
  - Textarea (auto-growing, Enter to submit, Shift+Enter for newline)
  - Send button (disabled while streaming)
  - Cancel button (shown while streaming)
```

#### `LiveStepTrace.tsx` (`ui/frontend/src/components/agents/LiveStepTrace.tsx`)

Real-time step visualization. Similar to the existing `RunStepInspector` but optimized for streaming:

- Steps appear one by one as events arrive
- In-progress steps show a spinner/pulse animation
- Completed steps show a checkmark and are collapsible (click to expand input/output)
- Tool calls show the tool name and input inline
- LLM calls show "Thinking..." while in progress, then the response summary

```
Props: { steps: StreamStep[], isStreaming: boolean }

Each step renders:
  ┌ Step ────────────────────────────────────────────────────────┐
  │ ● es_search("quarterly earnings" index:messages-*)   340ms  │  ← collapsed
  │ ▸ Click to expand input/output JSON                         │
  └─────────────────────────────────────────────────────────────┘
```

Differences from the existing `RunStepInspector`:
- Supports streaming state (spinner on "running" steps)
- More compact default view (tool name + input summary inline)
- Steps animate in with a subtle slide-down transition
- No accordion dependency — uses simpler collapsible divs for performance during rapid updates

### 5.6 Navigation Updates

Add a "Playground" button to the `AgentDetailPage` header (next to Clone/Edit/Delete):

```tsx
<Button variant="outline" size="sm" onClick={() => navigate(`/agents/${id}/playground`)}>
  <Play className="h-4 w-4 mr-1.5" />
  Playground
</Button>
```

### 5.7 Token Usage Display

The playground footer shows cumulative session stats:

```
Model: GPT-4o │ Temperature: 0.0 │ Max iterations: 10 │ Session: 3 runs, 4,231 tokens
```

Each completed run card shows:
```
── 4.2s │ 1,338 tokens (150 prompt + 298 completion) │ 3 iterations ──
```

---

## 6. Run Cancellation

### Flow

1. User clicks "Cancel" button in playground
2. Frontend calls `POST /api/v1/agent-runs/{run_id}/cancel`
3. UI Backend proxies to `POST /runs/{run_id}/cancel` on the runtime
4. Runtime sets the `cancelled` event on the `ManagedRun`
5. At the next iteration boundary, the executor checks the event:
   - Updates Run status to `cancelled` in the DB
   - Pushes `run_cancelled` event to the queue
   - Pushes sentinel `None` to close the stream
6. Frontend receives `run_cancelled`, updates UI

### Cancellation Check Points

The agent is checked for cancellation at two points:
1. **Before each LLM call** — in a custom `should_continue` function passed to the LangGraph agent
2. **Before each tool call** — in the `on_tool_start` callback

This ensures cancellation happens within one iteration, even if the LLM call itself is slow. For truly immediate cancellation during a slow LLM call, the background task can be cancelled via `task.cancel()`, but this is a last resort since it may leave the run in an inconsistent state.

---

## 7. File Inventory

### New Files

| File | Description |
|---|---|
| `agents/umbrella_agents/run_registry.py` | RunRegistry singleton managing in-flight runs |
| `agents/umbrella_agents/callbacks/streaming.py` | StreamingAuditCallback (DB + queue dual-write) |
| `agents/umbrella_agents/routers/stream.py` | SSE stream + cancel endpoints on runtime |
| `ui/frontend/src/pages/AgentPlaygroundPage.tsx` | Playground page component |
| `ui/frontend/src/components/agents/AgentPlayground.tsx` | Main playground container |
| `ui/frontend/src/components/agents/LiveStepTrace.tsx` | Real-time step visualization |
| `ui/frontend/src/hooks/useAgentStream.ts` | SSE hook for streaming agent execution |
| `agents/tests/test_streaming.py` | Tests for streaming execution + SSE |
| `agents/tests/test_run_registry.py` | Tests for RunRegistry |
| `ui/backend/tests/test_agent_streaming.py` | Tests for UI backend SSE proxy |

### Modified Files

| File | Changes |
|---|---|
| `agents/umbrella_agents/executor.py` | Add `execute_agent_streaming()` function |
| `agents/umbrella_agents/app.py` | Add RunRegistry to lifespan, register stream router |
| `agents/umbrella_agents/routers/execute.py` | Add `POST /execute-stream` endpoint |
| `agents/pyproject.toml` | Add `sse-starlette` dependency |
| `ui/backend/umbrella_ui/routers/agent_runs.py` | Add stream proxy + cancel endpoints |
| `ui/frontend/src/api/agents.ts` | Add `executeAgentStream()`, `agentRunStreamUrl()`, `cancelAgentRun()` |
| `ui/frontend/src/hooks/useAgents.ts` | Add `useExecuteAgentStream()` mutation (optional, may use `useAgentStream` instead) |
| `ui/frontend/src/pages/AgentDetailPage.tsx` | Add "Playground" button |
| `ui/frontend/src/App.tsx` | Add `/agents/:id/playground` route |
| `ui/frontend/src/lib/types.ts` | Add streaming-related types (optional — may be co-located with hook) |

---

## 8. Implementation Steps

### Step 1 — SSE Infrastructure (Agent Runtime)

**Files:** `run_registry.py`, `callbacks/streaming.py`, `routers/stream.py`, `app.py`, `pyproject.toml`

1. Add `sse-starlette` to `agents/pyproject.toml` dependencies
2. Create `RunRegistry` class in `run_registry.py`:
   - `_runs: dict[uuid.UUID, ManagedRun]`
   - Methods: `register()`, `get()`, `cancel()`, `remove()`, `active_count`
   - Auto-cleanup: remove runs 60s after terminal event
3. Create `StreamingAuditCallback` in `callbacks/streaming.py`:
   - Subclass `AsyncCallbackHandler`
   - Constructor takes `run_id`, `session_factory`, `event_queue`
   - Each callback method: write step to DB via `_write_step()` (reuse pattern from `audit.py`), then push event dict to `event_queue`
   - Event format: `{"event": "<event_type>", "data": {<payload>}}`
4. Create `stream.py` router:
   - `GET /runs/{run_id}/stream` — reads from queue, yields SSE via `EventSourceResponse`
   - `POST /runs/{run_id}/cancel` — calls `registry.cancel(run_id)`
   - Include heartbeat every 15s to keep connection alive
5. Update `app.py`:
   - Create `RunRegistry` in lifespan startup, attach to `app.state.run_registry`
   - Cancel all managed runs on shutdown
   - Include stream router

### Step 2 — Streaming Executor

**Files:** `executor.py`, `routers/execute.py`

1. Add `execute_agent_streaming()` to `executor.py`:
   - Same agent loading + building logic as `execute_agent()`
   - Takes additional params: `event_queue`, `cancelled`, `run_id`
   - Uses `StreamingAuditCallback` instead of `AuditCallbackHandler`
   - Pushes `run_started` event after creating Run record
   - Checks `cancelled.is_set()` before execution
   - Wraps execution in try/except to push terminal events
   - Pushes `None` sentinel at end
2. Add `POST /execute-stream` endpoint to `execute.py`:
   - Generate `run_id` upfront
   - Create queue + cancelled event
   - Create background task running `execute_agent_streaming()`
   - Register in `RunRegistry`
   - Return `{ run_id, status: "running" }` immediately
3. Enforce concurrency limit via `registry.active_count`

### Step 3 — UI Backend SSE Proxy

**Files:** `ui/backend/umbrella_ui/routers/agent_runs.py`

1. Add `POST /api/v1/agent-runs/stream`:
   - Proxy to runtime `POST /execute-stream`
   - Return `{ run_id, status }` to frontend
2. Add `GET /api/v1/agent-runs/{run_id}/stream`:
   - Open `httpx` streaming GET to runtime `GET /runs/{run_id}/stream`
   - Return `StreamingResponse` with `text/event-stream` content type
   - Set headers: `Cache-Control: no-cache`, `X-Accel-Buffering: no`
3. Add `POST /api/v1/agent-runs/{run_id}/cancel`:
   - Proxy to runtime `POST /runs/{run_id}/cancel`
   - Require supervisor role

### Step 4 — Frontend API + Hook

**Files:** `api/agents.ts`, `hooks/useAgentStream.ts`, `lib/types.ts`

1. Add API functions to `agents.ts`:
   - `executeAgentStream({ agent_id, input })` → POST
   - `agentRunStreamUrl(runId)` → returns SSE URL string
   - `cancelAgentRun(runId)` → POST
2. Add types for streaming state:
   - `PlaygroundRun`, `StreamStep` interfaces
3. Create `useAgentStream` hook:
   - Manages `EventSource` lifecycle
   - Exposes: `runs`, `currentRunId`, `isStreaming`, `startRun()`, `cancelRun()`
   - Handles all SSE event types
   - Auto-scrolls to bottom on new events
   - Cleanup on unmount (close EventSource)

### Step 5 — Playground UI

**Files:** `AgentPlaygroundPage.tsx`, `AgentPlayground.tsx`, `LiveStepTrace.tsx`

1. Create `AgentPlaygroundPage.tsx`:
   - Load agent via `useAgent(id)`
   - Render `AgentPlayground` component
   - Show agent name, model info in header
2. Create `AgentPlayground.tsx`:
   - Use `useAgentStream` hook
   - Render scrollable area with run cards
   - Render input textarea + send/cancel buttons
   - Auto-scroll to bottom when new steps arrive
   - Disable input while streaming
3. Create `LiveStepTrace.tsx`:
   - Render step list with streaming support
   - In-progress steps show animated pulse/spinner
   - Completed steps are collapsible
   - Tool calls show tool name + input preview inline
   - LLM calls show "Thinking..." → response summary
4. Add CSS transitions for step appearance animation

### Step 6 — Navigation + Route Wiring

**Files:** `App.tsx`, `AgentDetailPage.tsx`

1. Add route: `/agents/:id/playground` → `AgentPlaygroundPage`
2. Add "Playground" button to `AgentDetailPage` header
3. Import `AgentPlaygroundPage` in `App.tsx`

### Step 7 — Tests

**Files:** `agents/tests/test_streaming.py`, `agents/tests/test_run_registry.py`, `ui/backend/tests/test_agent_streaming.py`

1. `test_run_registry.py`:
   - Test register/get/cancel/remove lifecycle
   - Test active_count
   - Test cancellation sets event
2. `test_streaming.py`:
   - Test `StreamingAuditCallback` pushes events to queue
   - Test `StreamingAuditCallback` writes steps to DB
   - Test `execute_agent_streaming` pushes terminal events
   - Test cancellation produces `run_cancelled` event
   - Test SSE endpoint yields correct event format
3. `test_agent_streaming.py` (UI backend):
   - Test `POST /agent-runs/stream` proxies correctly
   - Test `POST /agent-runs/{id}/cancel` proxies correctly
   - Test SSE proxy forwards events

---

## 9. Testing Strategy

### Unit Tests

| Test | What it validates |
|---|---|
| `RunRegistry.register/get/cancel` | Registry CRUD and cancellation flag |
| `StreamingAuditCallback` events | Each callback method pushes correct event shape to queue |
| `StreamingAuditCallback` DB writes | Steps are persisted to DB alongside queue events |
| `execute_agent_streaming` lifecycle | run_started → steps → run_completed sequence |
| `execute_agent_streaming` failure | run_started → run_failed with error message |
| `execute_agent_streaming` cancel | run_started → run_cancelled when event set |

### Integration Tests

| Test | What it validates |
|---|---|
| SSE endpoint event format | Correct SSE formatting (event:, data:, newlines) |
| UI backend SSE proxy | Events flow through proxy without corruption |
| End-to-end stream with mock LLM | Full pipeline from POST → SSE events → terminal event |
| Concurrent run limit | 429 returned when limit exceeded |
| Heartbeat delivery | Heartbeat events sent during idle periods |

### Manual Testing Checklist

- [ ] Start a run from the playground, verify steps appear in real time
- [ ] Verify tool call inputs/outputs are shown correctly
- [ ] Cancel a running agent, verify it stops and shows cancelled status
- [ ] Close the browser tab during a run, reopen, verify run completed in run history
- [ ] Execute multiple runs in sequence, verify session history is maintained
- [ ] Test with a slow LLM (high temperature, long output) to verify streaming feels responsive
- [ ] Test with an agent that fails (bad tool config), verify error is shown cleanly
- [ ] Verify the Playground button appears on AgentDetailPage
- [ ] Verify the page is accessible directly via URL `/agents/:id/playground`
- [ ] Test on mobile viewport (textarea and steps should be usable)
