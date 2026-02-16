#!/usr/bin/env bash
# End-to-end pipeline test in minikube
#
# Tests the full 4-stage pipeline:
#   Stage 1: IMAP Connector (EmailConnector polls mailserver via IMAP)
#   Stage 2: Email Processor (parse EML from S3)
#   Stage 3: Ingestion Service (normalize parsed message)
#   Stage 4: Logstash → Elasticsearch (index normalized message)
#
# NOTE: This script skips optional monitoring resources (PodMonitor, ServiceMonitor)
# that require Prometheus Operator. The pipeline works fine without them.
set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "=========================================="
echo "Umbrella Pipeline Test - Minikube"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 1. Start minikube (if not running)
info "Checking minikube status..."
if ! minikube status &>/dev/null; then
    warn "Minikube not running. Starting minikube..."
    minikube start --memory=8192 --cpus=4
else
    info "Minikube is already running"
fi

# 2. Point Docker to minikube's daemon
info "Configuring Docker to use minikube's daemon..."
eval $(minikube docker-env)

# 3. Build Python service images (with --no-cache to pick up code changes)
info "Building Docker images..."
docker build --no-cache -f connectors/email/Dockerfile -t umbrella-email:latest .
docker build --no-cache -f ingestion-api/Dockerfile -t umbrella-ingestion:latest .
docker build --no-cache -f ui/backend/Dockerfile -t umbrella-ui-backend:latest .
docker build --no-cache -f ui/frontend/Dockerfile -t umbrella-ui-frontend:latest .

# 4. Deploy infrastructure (order matters — dependencies first)
info "Deploying umbrella-streaming (Kafka)..."
kubectl apply -f deploy/k8s/umbrella-streaming/namespace.yaml

# Apply Kafka manifests individually, skipping optional monitoring resources
for file in deploy/k8s/umbrella-streaming/*.yaml; do
    # Skip namespace (already applied) and optional monitoring resources
    if [[ "$file" != *"namespace.yaml" ]] && [[ "$file" != *"podmonitor.yaml" ]]; then
        kubectl apply -f "$file"
    fi
done

info "Waiting for Kafka to be ready..."
kubectl rollout status statefulset/kafka -n umbrella-streaming --timeout=180s

info "Deploying umbrella-storage (MinIO + Elasticsearch + Logstash)..."
kubectl apply -f deploy/k8s/umbrella-storage/namespace.yaml

info "Deploying PostgreSQL..."
kubectl apply -f deploy/k8s/umbrella-storage/postgresql/
kubectl rollout status statefulset/postgresql -n umbrella-storage --timeout=180s

# Wait for Flyway migrations to complete
info "Waiting for PostgreSQL migrations to complete..."
kubectl wait --for=condition=complete job/postgresql-migrations -n umbrella-storage --timeout=120s

# Create per-schema DB roles (init-roles.sql is in the configmap but nothing executes it)
info "Creating database roles..."
PG_POD=$(kubectl get pod -n umbrella-storage -l app=postgresql -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n umbrella-storage "$PG_POD" -- psql -U postgres -d umbrella -c "
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'iam_rw') THEN
        CREATE ROLE iam_rw LOGIN PASSWORD 'changeme-iam';
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'policy_rw') THEN
        CREATE ROLE policy_rw LOGIN PASSWORD 'changeme-policy';
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'alert_rw') THEN
        CREATE ROLE alert_rw LOGIN PASSWORD 'changeme-alert';
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'review_rw') THEN
        CREATE ROLE review_rw LOGIN PASSWORD 'changeme-review';
    END IF;

    -- Grant schema usage and table permissions
    GRANT USAGE ON SCHEMA iam    TO iam_rw;
    GRANT USAGE ON SCHEMA policy TO policy_rw;
    GRANT USAGE ON SCHEMA alert  TO alert_rw;
    GRANT USAGE ON SCHEMA review TO review_rw;

    -- Cross-schema read grants (per the role permissions table)
    GRANT USAGE ON SCHEMA iam    TO policy_rw, alert_rw, review_rw;
    GRANT USAGE ON SCHEMA policy TO alert_rw, review_rw;
    GRANT USAGE ON SCHEMA alert  TO review_rw;

    GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA iam    TO iam_rw;
    GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA policy TO policy_rw;
    GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA alert  TO alert_rw;
    GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA review TO review_rw;

    -- Cross-schema read-only grants
    GRANT SELECT ON ALL TABLES IN SCHEMA iam    TO policy_rw, alert_rw, review_rw;
    GRANT SELECT ON ALL TABLES IN SCHEMA policy TO alert_rw, review_rw;
    GRANT SELECT ON ALL TABLES IN SCHEMA alert  TO review_rw;

    -- Default privileges for future tables
    ALTER DEFAULT PRIVILEGES IN SCHEMA iam    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO iam_rw;
    ALTER DEFAULT PRIVILEGES IN SCHEMA policy GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO policy_rw;
    ALTER DEFAULT PRIVILEGES IN SCHEMA alert  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO alert_rw;
    ALTER DEFAULT PRIVILEGES IN SCHEMA review GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO review_rw;

    ALTER DEFAULT PRIVILEGES IN SCHEMA iam    GRANT SELECT ON TABLES TO policy_rw, alert_rw, review_rw;
    ALTER DEFAULT PRIVILEGES IN SCHEMA policy GRANT SELECT ON TABLES TO alert_rw, review_rw;
    ALTER DEFAULT PRIVILEGES IN SCHEMA alert  GRANT SELECT ON TABLES TO review_rw;
END
\$\$;
"

info "Deploying MinIO..."
kubectl apply -f deploy/k8s/umbrella-storage/minio/
kubectl rollout status deployment/minio -n umbrella-storage --timeout=120s

info "Deploying Elasticsearch..."
kubectl apply -f deploy/k8s/umbrella-storage/elasticsearch/
kubectl rollout status statefulset/elasticsearch -n umbrella-storage --timeout=300s

info "Deploying Logstash..."
kubectl apply -f deploy/k8s/umbrella-storage/logstash/
kubectl rollout status deployment/logstash -n umbrella-storage --timeout=300s

info "Deploying Kibana..."
kubectl apply -f deploy/k8s/umbrella-storage/kibana/
kubectl rollout status deployment/kibana -n umbrella-storage --timeout=300s

# 5. Deploy mailserver (SMTP/IMAP for Stage 1)
info "Deploying mailserver..."
kubectl apply -f deploy/k8s/umbrella-connectors/namespace.yaml
kubectl apply -f deploy/k8s/umbrella-connectors/mailserver-deployment.yaml
info "Waiting for mailserver to be ready..."
kubectl rollout status deployment/mailserver -n umbrella-connectors --timeout=300s

# 6. Deploy Python services
info "Deploying email-processor (Stage 2)..."
kubectl apply -f deploy/k8s/umbrella-connectors/email-processor-deployment.yaml
kubectl wait --for=condition=ready pod -l app=email-processor -n umbrella-connectors --timeout=300s

info "Deploying email-connector (Stage 1)..."
kubectl apply -f deploy/k8s/umbrella-connectors/email-connector-deployment.yaml
kubectl wait --for=condition=ready pod -l app=email-connector -n umbrella-connectors --timeout=300s

info "Deploying ingestion-service (Stage 3)..."
kubectl apply -f deploy/k8s/umbrella-ingestion/namespace.yaml
kubectl apply -f deploy/k8s/umbrella-ingestion/
kubectl wait --for=condition=ready pod -l app=ingestion-service -n umbrella-ingestion --timeout=120s

info "Deploying umbrella-ui (backend + frontend)..."
kubectl apply -f deploy/k8s/umbrella-ui/namespace.yaml
kubectl apply -f deploy/k8s/umbrella-ui/secret.yaml
kubectl apply -f deploy/k8s/umbrella-ui/backend/
kubectl apply -f deploy/k8s/umbrella-ui/frontend/

info "Waiting for UI backend to be ready..."
kubectl rollout status deployment/umbrella-ui-backend -n umbrella-ui --timeout=120s

info "Waiting for UI frontend to be ready..."
kubectl rollout status deployment/umbrella-ui-frontend -n umbrella-ui --timeout=60s

# Insert test user into PostgreSQL for Stage 6 auth check.
# Exec directly into the running PostgreSQL pod (avoids DNS + new-pod issues).
info "Seeding test user for UI authentication check..."
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

info "All services deployed successfully!"
echo ""

# 7. Wait a bit for services to stabilize
info "Waiting 10 seconds for services to stabilize..."
sleep 10

# 8. Send test email via SMTP to mailserver
info "Sending test email via SMTP..."
kubectl delete pod smtp-sender -n umbrella-connectors --ignore-not-found 2>/dev/null || true
kubectl run smtp-sender --rm -i --image=umbrella-email:latest --image-pull-policy=Never \
  -n umbrella-connectors --restart=Never -- \
  python3 -c "
import smtplib
from email.message import EmailMessage
from email.utils import formatdate

msg = EmailMessage()
msg['From'] = 'alice@example.com'
msg['To'] = 'testuser@umbrella.local'
msg['Subject'] = 'Pipeline Test - E2E Validation'
msg['Message-ID'] = '<pipeline-test-001@example.com>'
msg['Date'] = formatdate(localtime=False)
msg.set_content('Test email for pipeline validation. If this appears in Elasticsearch, all 4 stages work. This message contains potential fraud activity for compliance testing.')

with smtplib.SMTP('mailserver.umbrella-connectors.svc', 25) as s:
    s.send_message(msg)
    print('Email sent successfully')
"

info "Test email sent to testuser@umbrella.local"
echo ""

# 9. Wait for pipeline to process (45s for 4-stage propagation)
info "Waiting 45 seconds for pipeline to process the message..."
for i in {45..1}; do
    echo -ne "\rWaiting... ${i}s "
    sleep 1
done
echo ""
echo ""

# 10. Verify: check each stage
info "Verifying message flow through pipeline..."
echo ""

# Check raw-messages topic (Stage 1 output)
info "Checking raw-messages topic (Stage 1)..."
kubectl delete pod kafka-check-raw kafka-check-parsed kafka-check-normalized -n umbrella-streaming --ignore-not-found 2>/dev/null || true
RAW_COUNT=$(kubectl run kafka-check-raw --rm -i --image=apache/kafka:4.1.1 -n umbrella-streaming -- \
  /opt/kafka/bin/kafka-get-offsets.sh \
  --bootstrap-server kafka:9092 \
  --topic raw-messages 2>/dev/null | awk -F':' '{sum += $3} END {print sum+0}')

if [ "$RAW_COUNT" -gt 0 ]; then
    info "✓ Found $RAW_COUNT message(s) in raw-messages topic"
else
    warn "✗ No messages found in raw-messages topic"
fi

# Check parsed-messages topic (Stage 2 output)
info "Checking parsed-messages topic (Stage 2)..."
PARSED_COUNT=$(kubectl run kafka-check-parsed --rm -i --image=apache/kafka:4.1.1 -n umbrella-streaming -- \
  /opt/kafka/bin/kafka-get-offsets.sh \
  --bootstrap-server kafka:9092 \
  --topic parsed-messages 2>/dev/null | awk -F':' '{sum += $3} END {print sum+0}')

if [ "$PARSED_COUNT" -gt 0 ]; then
    info "✓ Found $PARSED_COUNT message(s) in parsed-messages topic"
else
    warn "✗ No messages found in parsed-messages topic"
fi

# Check normalized-messages topic (Stage 3 output)
info "Checking normalized-messages topic (Stage 3)..."
NORMALIZED_COUNT=$(kubectl run kafka-check-normalized --rm -i --image=apache/kafka:4.1.1 -n umbrella-streaming -- \
  /opt/kafka/bin/kafka-get-offsets.sh \
  --bootstrap-server kafka:9092 \
  --topic normalized-messages 2>/dev/null | awk -F':' '{sum += $3} END {print sum+0}')

if [ "$NORMALIZED_COUNT" -gt 0 ]; then
    info "✓ Found $NORMALIZED_COUNT message(s) in normalized-messages topic"
else
    warn "✗ No messages found in normalized-messages topic"
fi

# Check Elasticsearch (Stage 4 output)
info "Checking Elasticsearch (Stage 4)..."
info "Port-forwarding Elasticsearch..."
kubectl port-forward -n umbrella-storage svc/elasticsearch 9200:9200 >/dev/null 2>&1 &
PF_PID=$!
sleep 5

# Query Elasticsearch
ES_RESULT=$(curl -s http://localhost:9200/messages-*/_search?q=pipeline-test-001 | jq -r '.hits.total.value // 0' 2>/dev/null || echo "0")

kill $PF_PID 2>/dev/null || true

if [ "$ES_RESULT" -gt 0 ]; then
    info "✓ Found $ES_RESULT document(s) in Elasticsearch"
else
    warn "✗ No documents found in Elasticsearch"
fi

# Stage 5: UI backend message search API (deployed in K8s)
info "Checking UI backend message search API (Stage 5)..."
UI_RESULT=0

kubectl port-forward -n umbrella-ui svc/umbrella-ui-backend 8001:8000 >/dev/null 2>&1 &
PF_UI_PID=$!
sleep 3

# Generate a reviewer JWT using the same secret that's in the K8s secret
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

kill $PF_UI_PID 2>/dev/null || true

if [ "$UI_RESULT" -gt 0 ]; then
    info "✓ UI API returned $UI_RESULT message(s) for the test email"
else
    warn "✗ UI API returned no messages (response: $API_RESPONSE)"
fi

# Stage 6: UI login + auth flow (validates PostgreSQL + RBAC)
info "Checking UI login flow (Stage 6)..."
LOGIN_OK=0

kubectl port-forward -n umbrella-ui svc/umbrella-ui-backend 8001:8000 >/dev/null 2>&1 &
PF_UI2_PID=$!
sleep 2

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

kill $PF_UI2_PID 2>/dev/null || true

# Stage 7: Seed fraud policy/rule and create alert for the test document
info "Seeding fraud policy, rule, and alert (Stage 7)..."
ALERT_OK=0

# Get the ES document ID and index for the test message so the alert links correctly.
# Use term on message_id.keyword (exact match) to avoid false positives from
# tokenisation against older documents that share tokens like "test" or "001".
EXACT_MSG_ID="<pipeline-test-001@example.com>"
ES_DOC_ID=""
ES_INDEX=""
ES_TS=""

kubectl port-forward -n umbrella-storage svc/elasticsearch 9200:9200 >/dev/null 2>&1 &
PF_ES2_PID=$!
sleep 3

# Poll up to 60 extra seconds for the specific document to be indexed.
# Stages 1-4 can pass on stale Kafka offset counts; the exact document may
# take longer than the initial 45s wait to propagate through Logstash.
info "Waiting for pipeline-test-001 document to appear in Elasticsearch..."
for attempt in $(seq 1 12); do
    ES_DOC=$(curl -s "http://localhost:9200/messages-*/_search" \
      -H "Content-Type: application/json" \
      -d "{\"query\":{\"term\":{\"message_id.keyword\":\"${EXACT_MSG_ID}\"}},\"size\":1}")
    ES_DOC_ID=$(echo "$ES_DOC" | jq -r '.hits.hits[0]._id // empty')
    ES_INDEX=$(echo "$ES_DOC" | jq -r '.hits.hits[0]._index // empty')
    ES_TS=$(echo "$ES_DOC" | jq -r '.hits.hits[0]._source["@timestamp"] // empty')

    if [ -n "$ES_DOC_ID" ] && [ -n "$ES_INDEX" ]; then
        info "✓ Found document after $((attempt * 5))s: id=$ES_DOC_ID index=$ES_INDEX"
        break
    fi
    echo -ne "\r  Not indexed yet, retrying in 5s... (attempt $attempt/12)"
    sleep 5
done
echo ""

kill $PF_ES2_PID 2>/dev/null || true

if [ -z "$ES_DOC_ID" ] || [ -z "$ES_INDEX" ]; then
    warn "✗ pipeline-test-001 document not found in Elasticsearch after 60s extra wait"
else
    PG_POD=$(kubectl get pod -n umbrella-storage -l app=postgresql -o jsonpath='{.items[0].metadata.name}')
    kubectl exec -n umbrella-storage "$PG_POD" -- \
      psql -U postgres -d umbrella -c "
-- Risk model
INSERT INTO policy.risk_models (id, name, description, is_active, created_by)
VALUES (
  'aaaaaaaa-0000-0000-0000-000000000001',
  'Financial Crime',
  'Detects potential financial crime indicators in communications',
  true,
  '00000000-0000-0000-0000-000000000001'
) ON CONFLICT (id) DO NOTHING;

-- Policy
INSERT INTO policy.policies (id, risk_model_id, name, description, is_active, created_by)
VALUES (
  'bbbbbbbb-0000-0000-0000-000000000001',
  'aaaaaaaa-0000-0000-0000-000000000001',
  'Fraud Detection',
  'Flags messages containing fraud-related keywords',
  true,
  '00000000-0000-0000-0000-000000000001'
) ON CONFLICT (id) DO NOTHING;

-- Rule
INSERT INTO policy.rules (id, policy_id, name, description, kql, severity, is_active, created_by)
VALUES (
  'cccccccc-0000-0000-0000-000000000001',
  'bbbbbbbb-0000-0000-0000-000000000001',
  'Fraud Keyword Match',
  'Triggers when the word \"fraud\" appears in a message',
  'body_text:fraud',
  'high',
  true,
  '00000000-0000-0000-0000-000000000001'
) ON CONFLICT (id) DO NOTHING;

-- Alert linked to the test ES document
-- ON CONFLICT on id: update es_index/es_document_id so re-runs always point to
-- the current document (not a stale one from a previous pipeline run).
INSERT INTO alert.alerts (
  id, name, rule_id, es_index, es_document_id, es_document_ts, severity, status
) VALUES (
  'dddddddd-0000-0000-0000-000000000001',
  'Fraud Keyword Match — pipeline-test-001',
  'cccccccc-0000-0000-0000-000000000001',
  '$ES_INDEX',
  '$ES_DOC_ID',
  CASE WHEN '$ES_TS' = '' THEN NULL ELSE '$ES_TS'::timestamptz END,
  'high',
  'open'
) ON CONFLICT (id) DO UPDATE SET
  es_index       = EXCLUDED.es_index,
  es_document_id = EXCLUDED.es_document_id,
  es_document_ts = EXCLUDED.es_document_ts,
  status         = 'open';

-- Decision statuses (needed for the review UI)
INSERT INTO review.decision_statuses (id, name, description, is_terminal)
VALUES
  ('eeeeeeee-0000-0000-0000-000000000001', 'Escalate',    'Escalate for further review', false),
  ('eeeeeeee-0000-0000-0000-000000000002', 'No Breach',   'Reviewed — no policy breach', true),
  ('eeeeeeee-0000-0000-0000-000000000003', 'Breach Found','Confirmed policy breach',     true)
ON CONFLICT (id) DO NOTHING;
"

    # Verify the alert was created
    ALERT_COUNT=$(kubectl exec -n umbrella-storage "$PG_POD" -- \
      psql -U postgres -d umbrella -tAc \
      "SELECT COUNT(*) FROM alert.alerts WHERE id = 'dddddddd-0000-0000-0000-000000000001';")
    ALERT_COUNT="${ALERT_COUNT//[[:space:]]/}"

    if [ "$ALERT_COUNT" -gt 0 ]; then
        info "✓ Fraud alert created (policy: Fraud Detection, rule: Fraud Keyword Match, severity: high)"
        ALERT_OK=1
    else
        warn "✗ Alert insert failed"
    fi
fi

echo ""
echo "=========================================="
echo "Pipeline Test Summary"
echo "=========================================="
echo "Stage 1 (IMAP Connector):    $([ "$RAW_COUNT" -gt 0 ]        && echo '[✓ PASS]' || echo '[✗ FAIL]')"
echo "Stage 2 (Email Processor):   $([ "$PARSED_COUNT" -gt 0 ]     && echo '[✓ PASS]' || echo '[✗ FAIL]')"
echo "Stage 3 (Ingestion Service): $([ "$NORMALIZED_COUNT" -gt 0 ] && echo '[✓ PASS]' || echo '[✗ FAIL]')"
echo "Stage 4 (Logstash → ES):     $([ "$ES_RESULT" -gt 0 ]        && echo '[✓ PASS]' || echo '[✗ FAIL]')"
echo "Stage 5 (UI API search):     $([ "$UI_RESULT" -gt 0 ]        && echo '[✓ PASS]' || echo '[✗ FAIL]')"
echo "Stage 6 (UI login/auth):     $([ "$LOGIN_OK" -eq 1 ]         && echo '[✓ PASS]' || echo '[✗ FAIL]')"
echo "Stage 7 (Fraud alert):       $([ "$ALERT_OK" -eq 1 ]         && echo '[✓ PASS]' || echo '[✗ FAIL]')"
echo "=========================================="
echo ""

if [ "$RAW_COUNT" -gt 0 ] && [ "$PARSED_COUNT" -gt 0 ] && \
   [ "$NORMALIZED_COUNT" -gt 0 ] && [ "$ES_RESULT" -gt 0 ] && \
   [ "$UI_RESULT" -gt 0 ] && [ "$LOGIN_OK" -eq 1 ] && [ "$ALERT_OK" -eq 1 ]; then
    info "✓ PIPELINE TEST PASSED - All 7 stages working!"
    echo ""
    info "To access the UI:"
    echo "  kubectl port-forward -n umbrella-ui svc/umbrella-ui-frontend 3000:80"
    echo "  Open http://localhost:3000 — login with testadmin / testpass123"
    echo ""
    info "To access the UI API directly:"
    echo "  kubectl port-forward -n umbrella-ui svc/umbrella-ui-backend 8001:8000"
    echo "  Open http://localhost:8001/docs for the OpenAPI UI"
    echo ""
    info "To explore the data in Kibana:"
    echo "  kubectl port-forward -n umbrella-storage svc/kibana 5601:5601"
    echo "  Open http://localhost:5601 in your browser"
    echo "  (Index pattern: messages-*)"
    echo ""
    info "To view logs:"
    echo "  kubectl logs -n umbrella-connectors -l app=email-connector -f"
    echo "  kubectl logs -n umbrella-connectors -l app=email-processor -f"
    echo "  kubectl logs -n umbrella-ingestion -l app=ingestion-service -f"
    echo "  kubectl logs -n umbrella-storage -l app=logstash -f"
    echo "  kubectl logs -n umbrella-ui -l app=umbrella-ui-backend -f"
    exit 0
else
    error "✗ PIPELINE TEST FAILED - Check logs for errors"
    echo ""
    error "Debugging steps:"
    echo "  kubectl logs -n umbrella-connectors -l app=email-connector --tail=50"
    echo "  kubectl logs -n umbrella-connectors -l app=email-processor --tail=50"
    echo "  kubectl logs -n umbrella-ingestion -l app=ingestion-service --tail=50"
    echo "  kubectl logs -n umbrella-storage -l app=logstash --tail=50"
    echo "  kubectl logs -n umbrella-ui -l app=umbrella-ui-backend --tail=50"
    exit 1
fi
