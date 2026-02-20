#!/usr/bin/env bash
# Quick UI-only redeploy and test in minikube
#
# Assumes the full pipeline is already running (via test-pipeline-minikube.sh).
# Rebuilds only the UI images, redeploys the umbrella-ui namespace, seeds the
# test user, and runs Stage 5 (API search) + Stage 6 (login/auth) checks.
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
    kubectl apply -f deploy/k8s/umbrella-ui/ingress.yaml

    # Force pod restart to pick up new images
    info "Restarting UI pods..."
    kubectl rollout restart deployment/umbrella-ui-backend -n umbrella-ui
    kubectl rollout restart deployment/umbrella-ui-frontend -n umbrella-ui

    info "Waiting for UI backend..."
    kubectl rollout status deployment/umbrella-ui-backend -n umbrella-ui --timeout=120s

    info "Waiting for UI frontend..."
    kubectl rollout status deployment/umbrella-ui-frontend -n umbrella-ui --timeout=60s

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

# Cleanup port-forwards
kill $PF_PID $PF_FE_PID 2>/dev/null || true

# ── Summary ───────────────────────────────────────────────────────────────
echo ""
echo "=========================================="
echo "UI Test Summary"
echo "=========================================="
echo "Stage 5 (API search):      $([ "$UI_RESULT" -gt 0 ]  && echo '[✓ PASS]' || echo '[✗ FAIL]')"
echo "Stage 6 (Login/auth):      $([ "$LOGIN_OK" -eq 1 ]   && echo '[✓ PASS]' || echo '[✗ FAIL]')"
echo "Stage 7 (Frontend serves): $([ "$FRONTEND_OK" -eq 1 ] && echo '[✓ PASS]' || echo '[✗ FAIL]')"
echo "=========================================="
echo ""

if [ "$UI_RESULT" -gt 0 ] && [ "$LOGIN_OK" -eq 1 ] && [ "$FRONTEND_OK" -eq 1 ]; then
    info "✓ UI TEST PASSED"
    echo ""
    info "To access the UI:"
    echo "  kubectl port-forward -n umbrella-ui svc/umbrella-ui-frontend 3000:80"
    echo "  Open http://localhost:3000 — login with testadmin / testpass123"
    echo ""
    info "To access the API:"
    echo "  kubectl port-forward -n umbrella-ui svc/umbrella-ui-backend 8001:8000"
    echo "  Open http://localhost:8001/docs"
    exit 0
else
    error "✗ UI TEST FAILED"
    echo ""
    error "Debugging:"
    echo "  kubectl logs -n umbrella-ui -l app=umbrella-ui-backend --tail=50"
    echo "  kubectl logs -n umbrella-ui -l app=umbrella-ui-frontend --tail=50"
    echo "  kubectl describe pod -n umbrella-ui -l app=umbrella-ui-backend"
    exit 1
fi
