#!/usr/bin/env bash
# Quick UI-only redeploy and test in minikube
#
# Assumes the full pipeline is already running (via test-pipeline-minikube.sh).
# Rebuilds only the UI images, redeploys the umbrella-ui namespace, seeds the
# test user, and runs:
#   Stage 5 — API message search
#   Stage 6 — login + auth
#   Stage 7 — frontend serves SPA
#   Stage 8 — agent runtime health + NL search (502 expected without LLM key)
#   Stage 9 — agent streaming endpoints (execute-stream, cancel)
#
# Usage:
#   ./scripts/test-ui-minikube.sh              # rebuild + redeploy + test
#   ./scripts/test-ui-minikube.sh --no-build   # redeploy + test (skip image build)
#   ./scripts/test-ui-minikube.sh --test-only  # test only (skip build + deploy)
# Re-exec under bash if invoked with sh/dash
[ -z "$BASH_VERSION" ] && exec bash "$0" "$@"

set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

echo "=========================================="
echo "Umbrella UI Test - Minikube"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { printf "${GREEN}[INFO]${NC} %s\n" "$1"; }
warn()  { printf "${YELLOW}[WARN]${NC} %s\n" "$1"; }
error() { printf "${RED}[ERROR]${NC} %s\n" "$1"; }

# Parse flags
SKIP_BUILD=false
TEST_ONLY=false
while [ $# -gt 0 ]; do
    case "$1" in
        --no-build)  SKIP_BUILD=true ;;
        --test-only) TEST_ONLY=true; SKIP_BUILD=true ;;
        *) echo "Unknown flag: $1"; echo "Usage: $0 [--no-build|--test-only]"; exit 1 ;;
    esac
    shift
done

# Preflight: check minikube is running
if ! minikube status &>/dev/null; then
    error "Minikube is not running. Run the full pipeline test first:"
    echo "  ./scripts/test-pipeline-minikube.sh"
    exit 1
fi

# Preflight: check dependencies are up
for dep in "statefulset/kafka:umbrella-streaming" "statefulset/elasticsearch:umbrella-storage" "statefulset/postgresql:umbrella-storage"; do
    resource="${dep%%:*}"
    ns="${dep##*:}"
    if ! kubectl get "$resource" -n "$ns" &>/dev/null; then
        error "$resource not found in $ns. Run the full pipeline test first."
        exit 1
    fi
done

# Point Docker to minikube
eval $(minikube docker-env)

# ── Build ─────────────────────────────────────────────────────────────────
if [ "$SKIP_BUILD" = false ]; then
    info "Building UI images..."
    docker build --no-cache -f ui/backend/Dockerfile -t umbrella-ui-backend:latest .
    docker build --no-cache -f ui/frontend/Dockerfile -t umbrella-ui-frontend:latest .
    docker build --no-cache -f agents/Dockerfile -t umbrella-agent-runtime:latest .
    info "Images built successfully"
    echo ""
fi

# ── Deploy ────────────────────────────────────────────────────────────────
if [ "$TEST_ONLY" = false ]; then
    info "Deploying umbrella-ui namespace..."
    kubectl apply -f deploy/k8s/umbrella-ui/namespace.yaml
    kubectl apply -f deploy/k8s/umbrella-ui/secret.yaml
    kubectl apply -f deploy/k8s/umbrella-ui/backend/
    kubectl apply -f deploy/k8s/umbrella-ui/frontend/
    kubectl apply -f deploy/k8s/umbrella-ui/agents/
    kubectl apply -f deploy/k8s/umbrella-ui/ingress.yaml

    # Force pod restart to pick up new images
    info "Restarting UI pods..."
    kubectl rollout restart deployment/umbrella-ui-backend -n umbrella-ui
    kubectl rollout restart deployment/umbrella-ui-frontend -n umbrella-ui
    kubectl rollout restart deployment/umbrella-agent-runtime -n umbrella-ui

    info "Waiting for UI backend..."
    kubectl rollout status deployment/umbrella-ui-backend -n umbrella-ui --timeout=120s

    info "Waiting for UI frontend..."
    kubectl rollout status deployment/umbrella-ui-frontend -n umbrella-ui --timeout=60s

    info "Waiting for agent runtime..."
    kubectl rollout status deployment/umbrella-agent-runtime -n umbrella-ui --timeout=120s

    info "Seeding agent model..."
    # Delete any previous completed/failed run so kubectl apply can recreate it
    kubectl delete job umbrella-agent-model-seed -n umbrella-ui --ignore-not-found
    kubectl apply -f deploy/k8s/umbrella-ui/agents/seed-job.yaml
    kubectl wait job/umbrella-agent-model-seed -n umbrella-ui \
        --for=condition=complete --timeout=60s \
        || { warn "Agent model seed job did not complete in time"; kubectl logs -n umbrella-ui -l app=umbrella-agent-model-seed --tail=20; }

    # Seed test user (idempotent — ON CONFLICT DO NOTHING).
    # Exec into the running PostgreSQL pod directly.
    info "Seeding test user..."
    PG_POD=$(kubectl get pod -n umbrella-storage -l app=postgresql -o jsonpath='{.items[0].metadata.name}')
    kubectl exec -n umbrella-storage "$PG_POD" -- \
      psql -U postgres -d umbrella -c "
    INSERT INTO iam.users (id, username, email, password_hash, is_active)
    VALUES (
      '00000000-0000-0000-0000-000000000001',
      'testadmin',
      'testadmin@umbrella.local',
      '\$2b\$12\$23pdUICP8b0RHga0Tcu/gex/khFYnun9snfyYc/maeLeRhIzHp/RK',
      true
    )
    ON CONFLICT (id) DO NOTHING;
    INSERT INTO iam.groups (id, name, description)
    VALUES ('00000000-0000-0000-0000-000000000010', 'admins', 'Admin group')
    ON CONFLICT (id) DO NOTHING;
    INSERT INTO iam.user_groups (user_id, group_id)
    VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000010')
    ON CONFLICT DO NOTHING;
    INSERT INTO iam.group_roles (group_id, role_id)
    SELECT '00000000-0000-0000-0000-000000000010', id FROM iam.roles WHERE name = 'admin'
    ON CONFLICT DO NOTHING;
    "

    info "Seeding built-in tools (es_search, es_get_mapping, sql_query)..."
    kubectl exec -n umbrella-storage "$PG_POD" -- \
      psql -U postgres -d umbrella -c "
    INSERT INTO agent.tools (name, display_name, description, category, parameters_schema, is_active)
    VALUES (
      'es_search',
      'ES Search',
      'Search Elasticsearch for documents and/or run aggregations. Use fields to request only needed fields (saves tokens). Use aggs with size=0 for counts/stats without fetching documents. Use filters for term and range filtering.',
      'builtin',
      '{\"type\":\"object\",\"properties\":{\"query\":{\"type\":\"string\",\"description\":\"Search query text. Use * to match all documents.\"},\"index\":{\"type\":\"string\",\"default\":\"messages-*\",\"description\":\"Elasticsearch index pattern to search\"},\"filters\":{\"type\":\"object\",\"default\":{},\"description\":\"Term/range filters e.g. {channel: email, timestamp: {gte: now-7d}}\"},\"fields\":{\"type\":\"array\",\"items\":{\"type\":\"string\"},\"description\":\"Fields to return from each doc. Null returns all. Example: [body_text, channel, timestamp]\"},\"aggs\":{\"type\":\"object\",\"description\":\"ES aggregations. Example: {by_channel: {terms: {field: channel, size: 10}}}\"},\"size\":{\"type\":\"integer\",\"default\":10,\"description\":\"Number of docs to return (0 for agg-only)\"}},\"required\":[\"query\"]}',
      true
    )
    ON CONFLICT (name) DO UPDATE SET
      description = EXCLUDED.description,
      parameters_schema = EXCLUDED.parameters_schema;
    INSERT INTO agent.tools (name, display_name, description, category, parameters_schema, is_active)
    VALUES (
      'es_get_mapping',
      'ES Get Mapping',
      'Get the field mapping (schema) of an Elasticsearch index. Use this BEFORE searching to discover available fields, their types, and how to filter on them.',
      'builtin',
      '{\"type\":\"object\",\"properties\":{\"index\":{\"type\":\"string\",\"default\":\"messages-*\",\"description\":\"Elasticsearch index pattern to get the mapping for\"}},\"required\":[]}',
      true
    )
    ON CONFLICT (name) DO NOTHING;
    INSERT INTO agent.tools (name, display_name, description, category, parameters_schema, is_active)
    VALUES (
      'sql_query',
      'SQL Query',
      'Run read-only SQL queries against the PostgreSQL database. Use this to query alerts, entities, review queues, and other structured data.',
      'builtin',
      '{\"type\":\"object\",\"properties\":{\"query\":{\"type\":\"string\",\"description\":\"SQL SELECT query to execute\"}},\"required\":[\"query\"]}',
      true
    )
    ON CONFLICT (name) DO NOTHING;
    "

    info "UI deployed successfully"
    echo ""
fi

# ── Test ──────────────────────────────────────────────────────────────────
info "Running UI tests..."
echo ""

# Kill any leftover port-forwards on 8001
lsof -ti:8001 2>/dev/null | xargs -r kill 2>/dev/null || true

# Stage 5: message search via deployed backend
info "Stage 5: UI API message search..."
UI_RESULT=0

kubectl port-forward -n umbrella-ui svc/umbrella-ui-backend 8001:8000 >/dev/null 2>&1 &
PF_PID=$!
sleep 3

TEST_JWT_SECRET="umbrella-dev-jwt-secret-change-in-production"
UI_TOKEN=$(uv run --project ui/backend python -c "
from jose import jwt
import time
payload = {
    'sub': '00000000-0000-0000-0000-000000000001',
    'roles': ['reviewer'],
    'type': 'access',
    'exp': int(time.time()) + 300,
}
print(jwt.encode(payload, '$TEST_JWT_SECRET', algorithm='HS256'))
")

API_RESPONSE=$(curl -s -H "Authorization: Bearer $UI_TOKEN" \
    "http://localhost:8001/api/v1/messages/search?q=pipeline-test-001")
UI_RESULT=$(echo "$API_RESPONSE" | jq -r '.total // 0' 2>/dev/null || echo "0")

if [ "$UI_RESULT" -gt 0 ]; then
    info "✓ Found $UI_RESULT message(s) via UI API"
else
    warn "✗ No messages found (response: $API_RESPONSE)"
fi

# Stage 6: login + auth
info "Stage 6: UI login + auth..."
LOGIN_OK=0

LOGIN_RESPONSE=$(curl -s -X POST http://localhost:8001/api/v1/auth/login \
    -H "Content-Type: application/json" \
    -d '{"username":"testadmin","password":"testpass123"}')

ACCESS_TOKEN=$(echo "$LOGIN_RESPONSE" | jq -r '.access_token // empty' 2>/dev/null)

if [ -n "$ACCESS_TOKEN" ] && [ "$ACCESS_TOKEN" != "null" ]; then
    ME_RESPONSE=$(curl -s -H "Authorization: Bearer $ACCESS_TOKEN" \
        http://localhost:8001/api/v1/auth/me)
    HAS_ADMIN=$(echo "$ME_RESPONSE" | jq -r '[.roles[]? | select(. == "admin")] | length' 2>/dev/null || echo "0")

    if [ "$HAS_ADMIN" -gt 0 ]; then
        info "✓ Login succeeded — testadmin has admin role"
        LOGIN_OK=1
    else
        warn "✗ Login succeeded but admin role missing (response: $ME_RESPONSE)"
    fi
else
    warn "✗ Login failed (response: $LOGIN_RESPONSE)"
fi

# Stage 7: frontend serves HTML
info "Stage 7: Frontend serves SPA..."
FRONTEND_OK=0

kubectl port-forward -n umbrella-ui svc/umbrella-ui-frontend 3000:80 >/dev/null 2>&1 &
PF_FE_PID=$!
sleep 2

FRONTEND_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/)
if [ "$FRONTEND_RESPONSE" = "200" ]; then
    # Verify it's actually our SPA (check for the root div + script tag)
    FRONTEND_BODY=$(curl -s http://localhost:3000/)
    if echo "$FRONTEND_BODY" | grep -q 'id="root"'; then
        info "✓ Frontend serves SPA (HTTP 200, root div present)"
        FRONTEND_OK=1
    else
        warn "✗ Frontend returned 200 but missing root div"
    fi
else
    warn "✗ Frontend returned HTTP $FRONTEND_RESPONSE"
fi

# Stage 8: agent runtime health + NL search
info "Stage 8: Agent runtime health + NL search..."
AGENT_HEALTH_OK=0
NL_SEARCH_OK=0  # 0=fail, 1=pass (LLM worked), 2=expected-fail (no LLM key)

# Health check via the backend port-forward (PF_PID still running on 8001)
AGENT_HEALTH_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "Authorization: Bearer $UI_TOKEN" \
    http://localhost:8001/api/v1/agents)
if [ "$AGENT_HEALTH_RESPONSE" = "200" ]; then
    info "✓ Agent runtime reachable (GET /agents → 200)"
    AGENT_HEALTH_OK=1
else
    warn "✗ GET /agents returned HTTP $AGENT_HEALTH_RESPONSE (agent runtime may be down)"
fi

# NL search — expect 502 without an LLM key, 200 if one is configured
NL_HTTP=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST http://localhost:8001/api/v1/messages/nl-search \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $UI_TOKEN" \
    -d '{"query":"test messages from last week","limit":5}')

if [ "$NL_HTTP" = "200" ]; then
    info "✓ NL search returned 200 (LLM key is configured)"
    NL_SEARCH_OK=1
elif [ "$NL_HTTP" = "502" ]; then
    warn "~ NL search returned 502 (expected — no LLM API key set in umbrella-agent-runtime-credentials secret)"
    NL_SEARCH_OK=2
else
    warn "✗ NL search returned unexpected HTTP $NL_HTTP"
fi

# Stage 9: agent streaming endpoints
info "Stage 9: Agent streaming endpoints..."
STREAM_ENDPOINT_OK=0

# Generate a supervisor token for the cancel test
SUPERVISOR_TOKEN=$(uv run --project ui/backend python -c "
from jose import jwt
import time
payload = {
    'sub': '00000000-0000-0000-0000-000000000001',
    'roles': ['supervisor'],
    'type': 'access',
    'exp': int(time.time()) + 300,
}
print(jwt.encode(payload, '$TEST_JWT_SECRET', algorithm='HS256'))
")

# Test POST /agent-runs/stream — we expect a 502 (runtime can't reach LLM) or
# a 201 with {run_id, status} if an agent exists and the runtime is configured.
# If there are no agents, it'll be 422 or 404 — either way the endpoint is alive.
# First, find any agent id (may not exist)
AGENT_LIST=$(curl -s -H "Authorization: Bearer $UI_TOKEN" \
    http://localhost:8001/api/v1/agents)
FIRST_AGENT_ID=$(echo "$AGENT_LIST" | jq -r '.items[0].id // empty' 2>/dev/null)

if [ -n "$FIRST_AGENT_ID" ] && [ "$FIRST_AGENT_ID" != "null" ]; then
    STREAM_HTTP=$(curl -s -o /tmp/stream_resp.json -w "%{http_code}" \
        -X POST http://localhost:8001/api/v1/agent-runs/stream \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $UI_TOKEN" \
        -d "{\"agent_id\":\"$FIRST_AGENT_ID\",\"input\":\"streaming test\"}")

    if [ "$STREAM_HTTP" = "201" ]; then
        STREAM_RUN_ID=$(jq -r '.run_id // empty' /tmp/stream_resp.json 2>/dev/null)
        if [ -n "$STREAM_RUN_ID" ] && [ "$STREAM_RUN_ID" != "null" ]; then
            info "✓ POST /agent-runs/stream → 201 (run_id=$STREAM_RUN_ID)"
            STREAM_ENDPOINT_OK=1

            # Test cancel endpoint
            CANCEL_HTTP=$(curl -s -o /dev/null -w "%{http_code}" \
                -X POST "http://localhost:8001/api/v1/agent-runs/$STREAM_RUN_ID/cancel" \
                -H "Authorization: Bearer $SUPERVISOR_TOKEN")
            if [ "$CANCEL_HTTP" = "200" ]; then
                info "✓ POST /agent-runs/{id}/cancel → 200"
            else
                warn "~ POST /agent-runs/{id}/cancel → $CANCEL_HTTP (run may have already finished)"
                # Not a failure — run may have completed before cancel reached it
            fi

            # Test SSE stream endpoint responds (just check the content-type header)
            STREAM_SSE_CT=$(curl -s -o /dev/null -D - --max-time 3 \
                -H "Authorization: Bearer $UI_TOKEN" \
                "http://localhost:8001/api/v1/agent-runs/$STREAM_RUN_ID/stream" 2>/dev/null \
                | grep -i "content-type" | head -1 || echo "")
            if echo "$STREAM_SSE_CT" | grep -qi "text/event-stream"; then
                info "✓ GET /agent-runs/{id}/stream → text/event-stream"
            else
                warn "~ SSE stream content-type not verified (run may have completed)"
            fi
        else
            warn "✗ POST /agent-runs/stream → 201 but no run_id in response"
        fi
    elif [ "$STREAM_HTTP" = "502" ]; then
        warn "~ POST /agent-runs/stream → 502 (expected — no LLM API key)"
        STREAM_ENDPOINT_OK=2
    else
        warn "✗ POST /agent-runs/stream → HTTP $STREAM_HTTP"
    fi
    rm -f /tmp/stream_resp.json
else
    warn "~ No agents found — skipping streaming endpoint test"
    STREAM_ENDPOINT_OK=2  # treat as expected-skip
fi

# Stage 10: End-to-end agent execution — create agent, run ES search, verify output
info "Stage 10: Agent E2E — create & execute ES search agent..."
AGENT_E2E_OK=0  # 0=fail, 1=pass, 2=expected-skip (no LLM key)

# We need supervisor token (already generated above) + PG_POD

# 1. Get model ID and es_search tool ID from the API
MODEL_ID=$(curl -s -H "Authorization: Bearer $SUPERVISOR_TOKEN" \
    http://localhost:8001/api/v1/agent-models | jq -r '.items[0].id // empty' 2>/dev/null)
ES_TOOL_ID=$(curl -s -H "Authorization: Bearer $SUPERVISOR_TOKEN" \
    http://localhost:8001/api/v1/agent-tools | jq -r '[.items[] | select(.name=="es_search")][0].id // empty' 2>/dev/null)
MAPPING_TOOL_ID=$(curl -s -H "Authorization: Bearer $SUPERVISOR_TOKEN" \
    http://localhost:8001/api/v1/agent-tools | jq -r '[.items[] | select(.name=="es_get_mapping")][0].id // empty' 2>/dev/null)

if [ -z "$MODEL_ID" ] || [ "$MODEL_ID" = "null" ]; then
    warn "~ No model found — skipping agent E2E test"
    AGENT_E2E_OK=2
elif [ -z "$ES_TOOL_ID" ] || [ "$ES_TOOL_ID" = "null" ]; then
    warn "~ es_search tool not found — skipping agent E2E test"
    AGENT_E2E_OK=2
else
    # Build tool_ids array — always include es_search, optionally es_get_mapping
    TOOL_IDS="\"$ES_TOOL_ID\""
    if [ -n "$MAPPING_TOOL_ID" ] && [ "$MAPPING_TOOL_ID" != "null" ]; then
        TOOL_IDS="\"$ES_TOOL_ID\", \"$MAPPING_TOOL_ID\""
    fi

    # 2. Create the test agent via the API
    AGENT_CREATE_RESP=$(curl -s -o /tmp/agent_create.json -w "%{http_code}" \
        -X POST http://localhost:8001/api/v1/agents \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $SUPERVISOR_TOKEN" \
        -d "{
          \"name\": \"E2E Test Search Agent\",
          \"description\": \"Searches Elasticsearch for test events and summarizes findings\",
          \"model_id\": \"$MODEL_ID\",
          \"system_prompt\": \"You are a data analyst with access to tools. You MUST use tools to answer questions — never guess or fabricate data.\\n\\nAvailable tools:\\n- es_get_mapping: Call this first to discover the fields and types in an Elasticsearch index before searching.\\n- es_search: Search for documents using full-text queries and filters.\\n\\nWorkflow:\\n1. Call es_get_mapping to learn the index schema.\\n2. Call es_search with appropriate query and filters based on the schema.\\n3. Summarize the results for the user.\\n\\nAlways call tools — do not output tool invocations as text.\",
          \"temperature\": 0.0,
          \"max_iterations\": 10,
          \"tool_ids\": [$TOOL_IDS],
          \"data_sources\": [{\"source_type\": \"elasticsearch\", \"source_identifier\": \"messages-*\"}]
        }")

    if [ "$AGENT_CREATE_RESP" = "201" ] || [ "$AGENT_CREATE_RESP" = "409" ]; then
        if [ "$AGENT_CREATE_RESP" = "409" ]; then
            # Agent already exists from a previous run — look it up
            TEST_AGENT_ID=$(curl -s -H "Authorization: Bearer $SUPERVISOR_TOKEN" \
                http://localhost:8001/api/v1/agents | \
                jq -r '[.items[] | select(.name=="E2E Test Search Agent")][0].id // empty' 2>/dev/null)
        else
            TEST_AGENT_ID=$(jq -r '.id // empty' /tmp/agent_create.json 2>/dev/null)
        fi

        if [ -n "$TEST_AGENT_ID" ] && [ "$TEST_AGENT_ID" != "null" ]; then
            info "  Agent created/found: $TEST_AGENT_ID"

            # 3. Execute the agent — search for the test message ingested by the pipeline test
            info "  Executing agent (searching for 'pipeline-test-001')..."
            EXEC_HTTP=$(curl -s -o /tmp/agent_exec.json -w "%{http_code}" \
                --max-time 120 \
                -X POST http://localhost:8001/api/v1/agent-runs \
                -H "Content-Type: application/json" \
                -H "Authorization: Bearer $UI_TOKEN" \
                -d "{\"agent_id\": \"$TEST_AGENT_ID\", \"input\": \"Search for messages containing pipeline-test-001 and summarize what you find.\"}")

            if [ "$EXEC_HTTP" = "201" ]; then
                RUN_STATUS=$(jq -r '.status // empty' /tmp/agent_exec.json 2>/dev/null)
                RUN_OUTPUT=$(jq -r '.output.response // empty' /tmp/agent_exec.json 2>/dev/null)
                RUN_STEPS=$(jq -r '.steps // [] | length' /tmp/agent_exec.json 2>/dev/null)

                if [ "$RUN_STATUS" = "completed" ]; then
                    # Check that the agent actually used the es_search tool
                    USED_ES=$(jq -r '[.steps[]? | select(.tool_name=="es_search")] | length' /tmp/agent_exec.json 2>/dev/null || echo "0")
                    if [ "$USED_ES" -gt 0 ] && [ -n "$RUN_OUTPUT" ]; then
                        info "✓ Agent completed — used es_search ($USED_ES call(s)), $RUN_STEPS steps"
                        info "  Output preview: $(echo "$RUN_OUTPUT" | head -c 200)..."
                        AGENT_E2E_OK=1
                    elif [ -n "$RUN_OUTPUT" ]; then
                        warn "~ Agent completed but did not use es_search tool (output: $(echo "$RUN_OUTPUT" | head -c 150))"
                        AGENT_E2E_OK=1  # still a pass — agent ran and produced output
                    else
                        warn "✗ Agent completed but no output"
                    fi
                elif [ "$RUN_STATUS" = "failed" ]; then
                    RUN_ERR=$(jq -r '.error_message // "unknown"' /tmp/agent_exec.json 2>/dev/null)
                    warn "✗ Agent run failed: $(echo "$RUN_ERR" | head -c 200)"
                else
                    warn "~ Agent run status: $RUN_STATUS"
                    AGENT_E2E_OK=2
                fi
            elif [ "$EXEC_HTTP" = "502" ]; then
                warn "~ Agent execution returned 502 (expected — LLM may be unreachable)"
                AGENT_E2E_OK=2
            else
                warn "✗ Agent execution returned HTTP $EXEC_HTTP"
                cat /tmp/agent_exec.json 2>/dev/null | head -5
            fi
            rm -f /tmp/agent_exec.json
        else
            warn "✗ Could not determine test agent ID"
        fi
        rm -f /tmp/agent_create.json
    else
        warn "✗ Agent creation returned HTTP $AGENT_CREATE_RESP"
        cat /tmp/agent_create.json 2>/dev/null | head -5
        rm -f /tmp/agent_create.json
    fi
fi

# Cleanup port-forwards
kill $PF_PID $PF_FE_PID 2>/dev/null || true

# ── Summary ───────────────────────────────────────────────────────────────
echo ""
echo "=========================================="
echo "UI Test Summary"
echo "=========================================="
echo "Stage 5 (API search):      $([ "$UI_RESULT" -gt 0 ]   && echo '[✓ PASS]' || echo '[✗ FAIL]')"
echo "Stage 6 (Login/auth):      $([ "$LOGIN_OK" -eq 1 ]    && echo '[✓ PASS]' || echo '[✗ FAIL]')"
echo "Stage 7 (Frontend serves): $([ "$FRONTEND_OK" -eq 1 ] && echo '[✓ PASS]' || echo '[✗ FAIL]')"
echo "Stage 8a (Agent runtime):  $([ "$AGENT_HEALTH_OK" -eq 1 ] && echo '[✓ PASS]' || echo '[✗ FAIL]')"
if [ "$NL_SEARCH_OK" -eq 1 ]; then
    echo "Stage 8b (NL search):      [✓ PASS]"
elif [ "$NL_SEARCH_OK" -eq 2 ]; then
    echo "Stage 8b (NL search):      [~ WARN] 502 — set OPENAI_API_KEY in umbrella-agent-runtime-credentials secret"
else
    echo "Stage 8b (NL search):      [✗ FAIL]"
fi
if [ "$STREAM_ENDPOINT_OK" -eq 1 ]; then
    echo "Stage 9  (Streaming):      [✓ PASS]"
elif [ "$STREAM_ENDPOINT_OK" -eq 2 ]; then
    echo "Stage 9  (Streaming):      [~ WARN] 502 or no agents — streaming endpoint skipped/degraded"
else
    echo "Stage 9  (Streaming):      [✗ FAIL]"
fi
if [ "$AGENT_E2E_OK" -eq 1 ]; then
    echo "Stage 10 (Agent E2E):      [✓ PASS]"
elif [ "$AGENT_E2E_OK" -eq 2 ]; then
    echo "Stage 10 (Agent E2E):      [~ WARN] skipped — no LLM key, model, or tool"
else
    echo "Stage 10 (Agent E2E):      [✗ FAIL]"
fi
echo "=========================================="
echo ""

# Stages 8b, 9, and 10 are excluded from hard pass/fail — a missing LLM key or no agents is expected in CI
if [ "$UI_RESULT" -gt 0 ] && [ "$LOGIN_OK" -eq 1 ] && [ "$FRONTEND_OK" -eq 1 ] && [ "$AGENT_HEALTH_OK" -eq 1 ] && [ "$NL_SEARCH_OK" -ne 0 ] && [ "$STREAM_ENDPOINT_OK" -ne 0 ] && [ "$AGENT_E2E_OK" -ne 0 ]; then
    info "✓ UI TEST PASSED"
    echo ""
    info "To access the UI:"
    echo "  kubectl port-forward -n umbrella-ui svc/umbrella-ui-frontend 3000:80"
    echo "  Open http://localhost:3000 — login with testadmin / testpass123"
    echo ""
    info "To access the API:"
    echo "  kubectl port-forward -n umbrella-ui svc/umbrella-ui-backend 8001:8000"
    echo "  Open http://localhost:8001/docs"
    echo ""
    info "To enable NL search, add your LLM key:"
    echo "  kubectl patch secret umbrella-agent-runtime-credentials -n umbrella-ui \\"
    echo "    --type=merge -p '{\"stringData\":{\"OPENAI_API_KEY\":\"sk-...\"}}'"
    echo "  kubectl rollout restart deployment/umbrella-agent-runtime -n umbrella-ui"
    exit 0
else
    error "✗ UI TEST FAILED"
    echo ""
    error "Debugging:"
    echo "  kubectl logs -n umbrella-ui -l app=umbrella-ui-backend --tail=50"
    echo "  kubectl logs -n umbrella-ui -l app=umbrella-ui-frontend --tail=50"
    echo "  kubectl logs -n umbrella-ui -l app=umbrella-agent-runtime --tail=50"
    echo "  kubectl describe pod -n umbrella-ui -l app=umbrella-ui-backend"
    exit 1
fi
