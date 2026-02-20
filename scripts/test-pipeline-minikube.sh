#!/usr/bin/env bash
# End-to-end pipeline test in minikube.
#
# Assumes the cluster is already deployed (run scripts/deploy-minikube.sh first).
#
# This script:
#   1. Creates per-schema DB roles
#   2. Seeds a test user for auth
#   3. Sends a test email through the pipeline
#   4. Verifies all 10 stages:
#      Stage 1: IMAP Connector (EmailConnector polls mailserver via IMAP)
#      Stage 2: Email Processor (parse EML from S3)
#      Stage 3: Ingestion Service (normalize parsed message)
#      Stage 4: Logstash → Elasticsearch (index normalized message)
#      Stage 5: UI API message search (query ES via backend)
#      Stage 6: UI login + auth (PostgreSQL + RBAC)
#      Stage 7: Seed fraud policy/rule/alert (PostgreSQL)
#      Stage 8: Alert review E2E (submit decision + verify audit log)
#      Stage 9: Entity resolution (CRUD entities + handles via API)
#      Stage 10: Batch alert generation (generate alerts from policies via API)
# Re-exec under bash if invoked with sh/dash
[ -z "$BASH_VERSION" ] && exec bash "$0" "$@"

set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

echo "=========================================="
echo "Umbrella Pipeline Test - Minikube"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { printf "${GREEN}[INFO]${NC} %s\n" "$1"; }
warn()  { printf "${YELLOW}[WARN]${NC} %s\n" "$1"; }
error() { printf "${RED}[ERROR]${NC} %s\n" "$1"; }

# Verify the cluster is reachable before doing anything
if ! kubectl get ns umbrella-storage &>/dev/null; then
    error "umbrella-storage namespace not found. Run scripts/deploy-minikube.sh first."
    exit 1
fi

# ─── Step 1: Create per-schema DB roles ───────────────────────────────────────
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
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'entity_rw') THEN
        CREATE ROLE entity_rw LOGIN PASSWORD 'changeme-entity';
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

    -- Entity schema grants (only if V7 migration has been applied)
    IF EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = 'entity') THEN
        GRANT USAGE ON SCHEMA entity TO entity_rw;
        GRANT USAGE ON SCHEMA iam    TO entity_rw;
        GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA entity TO entity_rw;
        GRANT SELECT ON ALL TABLES IN SCHEMA iam TO entity_rw;
        ALTER DEFAULT PRIVILEGES IN SCHEMA entity GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO entity_rw;
        ALTER DEFAULT PRIVILEGES IN SCHEMA iam    GRANT SELECT ON TABLES TO entity_rw;
    END IF;
END
\$\$;
"

# ─── Step 2: Seed test user ───────────────────────────────────────────────────
info "Seeding test user for UI authentication check..."
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

info "All roles and seed data applied."
echo ""

# ─── Step 3: Wait for services to stabilise ───────────────────────────────────
info "Waiting 10 seconds for services to stabilize..."
sleep 10

# ─── Step 4: Send test email via SMTP ─────────────────────────────────────────
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

# ─── Step 5: Wait for pipeline to process ────────────────────────────────────
info "Waiting 45 seconds for pipeline to process the message..."
for i in {45..1}; do
    echo -ne "\rWaiting... ${i}s "
    sleep 1
done
echo ""
echo ""

# ─── Stage verification ───────────────────────────────────────────────────────
info "Verifying message flow through pipeline..."
echo ""

# Stage 1: raw-messages topic
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

# Stage 2: parsed-messages topic
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

# Stage 3: normalized-messages topic
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

# Stage 4: Elasticsearch
info "Checking Elasticsearch (Stage 4)..."
info "Port-forwarding Elasticsearch..."
kubectl port-forward -n umbrella-storage svc/elasticsearch 9200:9200 >/dev/null 2>&1 &
PF_PID=$!
sleep 5

ES_RESULT=$(curl -s http://localhost:9200/messages-*/_search?q=pipeline-test-001 | jq -r '.hits.total.value // 0' 2>/dev/null || echo "0")

kill $PF_PID 2>/dev/null || true

if [ "$ES_RESULT" -gt 0 ]; then
    info "✓ Found $ES_RESULT document(s) in Elasticsearch"
else
    warn "✗ No documents found in Elasticsearch"
fi

# Stage 5: UI backend message search API
info "Checking UI backend message search API (Stage 5)..."
UI_RESULT=0

kubectl port-forward -n umbrella-ui svc/umbrella-ui-backend 8001:8000 >/dev/null 2>&1 &
PF_UI_PID=$!
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

kill $PF_UI_PID 2>/dev/null || true

if [ "$UI_RESULT" -gt 0 ]; then
    info "✓ UI API returned $UI_RESULT message(s) for the test email"
else
    warn "✗ UI API returned no messages (response: $API_RESPONSE)"
fi

# Stage 6: UI login + auth
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

# Stage 7: Seed fraud policy/rule and create alert
info "Seeding fraud policy, rule, and alert (Stage 7)..."
ALERT_OK=0

EXACT_MSG_ID="<pipeline-test-001@example.com>"
ES_DOC_ID=""
ES_INDEX=""
ES_TS=""

kubectl port-forward -n umbrella-storage svc/elasticsearch 9200:9200 >/dev/null 2>&1 &
PF_ES2_PID=$!
sleep 3

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

-- Rule 1: manually-alerted rule (for Stage 8 review flow)
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

-- Rule 2: for batch alert generation test (Stage 10) — no manual alert inserted
INSERT INTO policy.rules (id, policy_id, name, description, kql, severity, is_active, created_by)
VALUES (
  'cccccccc-0000-0000-0000-000000000002',
  'bbbbbbbb-0000-0000-0000-000000000001',
  'Compliance Keyword Match',
  'Triggers when the word \"compliance\" appears in a message',
  'body_text:compliance',
  'medium',
  true,
  '00000000-0000-0000-0000-000000000001'
) ON CONFLICT (id) DO NOTHING;

-- Alert linked to the test ES document
-- ON CONFLICT on id: update es_index/es_document_id so re-runs always point to
-- the current document (not a stale one from a previous pipeline run).
INSERT INTO alert.alerts (
  id, name, rule_id, es_index, es_document_id, es_document_ts, severity, status, channel
) VALUES (
  'dddddddd-0000-0000-0000-000000000001',
  'Fraud Keyword Match — pipeline-test-001',
  'cccccccc-0000-0000-0000-000000000001',
  '$ES_INDEX',
  '$ES_DOC_ID',
  CASE WHEN '$ES_TS' = '' THEN NULL ELSE '$ES_TS'::timestamptz END,
  'high',
  'open',
  'email'
) ON CONFLICT (id) DO UPDATE SET
  es_index       = EXCLUDED.es_index,
  es_document_id = EXCLUDED.es_document_id,
  es_document_ts = EXCLUDED.es_document_ts,
  channel        = EXCLUDED.channel,
  status         = 'open';

-- Decision statuses (needed for the review UI)
INSERT INTO review.decision_statuses (id, name, description, is_terminal)
VALUES
  ('eeeeeeee-0000-0000-0000-000000000001', 'Escalate',    'Escalate for further review', false),
  ('eeeeeeee-0000-0000-0000-000000000002', 'No Breach',   'Reviewed — no policy breach', true),
  ('eeeeeeee-0000-0000-0000-000000000003', 'Breach Found','Confirmed policy breach',     true)
ON CONFLICT (id) DO NOTHING;
"

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

# Stage 8: Alert review E2E
info "End-to-end alert review flow (Stage 8)..."
REVIEW_OK=0

if [ "$LOGIN_OK" -eq 1 ] && [ "$ALERT_OK" -eq 1 ]; then
    kubectl port-forward -n umbrella-ui svc/umbrella-ui-backend 8001:8000 >/dev/null 2>&1 &
    PF_UI3_PID=$!
    sleep 3

    ALERT_ID="dddddddd-0000-0000-0000-000000000001"
    DECISION_STATUS_ID="eeeeeeee-0000-0000-0000-000000000001"  # "Escalate" (non-terminal)

    # 8a. GET alert detail
    ALERT_DETAIL=$(curl -s -H "Authorization: Bearer $ACCESS_TOKEN" \
        "http://localhost:8001/api/v1/alerts/$ALERT_ID")
    ALERT_NAME=$(echo "$ALERT_DETAIL" | jq -r '.name // empty' 2>/dev/null)

    if [ -n "$ALERT_NAME" ]; then
        info "  ✓ Fetched alert: $ALERT_NAME"
    else
        warn "  ✗ Could not fetch alert detail (response: $ALERT_DETAIL)"
    fi

    # 8b. POST decision
    DECISION_RESPONSE=$(curl -s -X POST \
        -H "Authorization: Bearer $ACCESS_TOKEN" \
        -H "Content-Type: application/json" \
        "http://localhost:8001/api/v1/alerts/$ALERT_ID/decisions" \
        -d "{\"status_id\":\"$DECISION_STATUS_ID\",\"comment\":\"E2E pipeline test — escalating for review\"}")
    DECISION_ID=$(echo "$DECISION_RESPONSE" | jq -r '.id // empty' 2>/dev/null)

    if [ -n "$DECISION_ID" ] && [ "$DECISION_ID" != "null" ]; then
        info "  ✓ Decision submitted: id=$DECISION_ID"
    else
        warn "  ✗ Decision submission failed (response: $DECISION_RESPONSE)"
    fi

    # 8c. GET audit log
    if [ -n "$DECISION_ID" ] && [ "$DECISION_ID" != "null" ]; then
        AUDIT_RESPONSE=$(curl -s -H "Authorization: Bearer $ACCESS_TOKEN" \
            "http://localhost:8001/api/v1/audit-log?alert_id=$ALERT_ID&limit=5")
        AUDIT_COUNT=$(echo "$AUDIT_RESPONSE" | jq -r '.total // 0' 2>/dev/null || echo "0")

        if [ "$AUDIT_COUNT" -gt 0 ]; then
            info "  ✓ Audit log contains $AUDIT_COUNT entry(s) for this alert"
            REVIEW_OK=1
        else
            warn "  ✗ Audit log is empty (response: $AUDIT_RESPONSE)"
        fi
    fi

    kill $PF_UI3_PID 2>/dev/null || true
else
    warn "  ⊘ Skipped — Stage 6 (login) or Stage 7 (alert) did not pass"
fi

# Stage 9: Entity resolution CRUD
info "Entity resolution CRUD (Stage 9)..."
ENTITY_OK=0

if [ "$LOGIN_OK" -eq 1 ]; then
    kubectl port-forward -n umbrella-ui svc/umbrella-ui-backend 8001:8000 >/dev/null 2>&1 &
    PF_UI4_PID=$!
    sleep 3

    # 9a. Create entity (or find existing on re-runs)
    CREATE_ENTITY_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST \
        -H "Authorization: Bearer $ACCESS_TOKEN" \
        -H "Content-Type: application/json" \
        "http://localhost:8001/api/v1/entities" \
        -d '{
            "display_name": "Alice (Test Sender)",
            "entity_type": "person",
            "handles": [
                {"handle_type": "email", "handle_value": "alice@example.com", "is_primary": true}
            ],
            "attributes": [
                {"attr_key": "department", "attr_value": "Trading"},
                {"attr_key": "company", "attr_value": "Example Corp"}
            ]
        }')
    CREATE_HTTP_CODE=$(echo "$CREATE_ENTITY_RESPONSE" | tail -1)
    CREATE_BODY=$(echo "$CREATE_ENTITY_RESPONSE" | sed '$d')
    ENTITY_ID=$(echo "$CREATE_BODY" | jq -r '.id // empty' 2>/dev/null)

    if [ -n "$ENTITY_ID" ] && [ "$ENTITY_ID" != "null" ]; then
        info "  ✓ Entity created: id=$ENTITY_ID"
    elif [ "$CREATE_HTTP_CODE" = "409" ]; then
        SEARCH_RESPONSE=$(curl -s -H "Authorization: Bearer $ACCESS_TOKEN" \
            "http://localhost:8001/api/v1/entities?search=Alice")
        ENTITY_ID=$(echo "$SEARCH_RESPONSE" | jq -r '.items[0].id // empty' 2>/dev/null)
        if [ -n "$ENTITY_ID" ] && [ "$ENTITY_ID" != "null" ]; then
            info "  ✓ Entity already exists (re-run): id=$ENTITY_ID"
        else
            warn "  ✗ Entity exists (409) but could not find it via search"
        fi
    else
        warn "  ✗ Entity creation failed (response: $CREATE_BODY)"
    fi

    # 9b. GET entity and verify handles + attributes
    if [ -n "$ENTITY_ID" ] && [ "$ENTITY_ID" != "null" ]; then
        GET_ENTITY_RESPONSE=$(curl -s -H "Authorization: Bearer $ACCESS_TOKEN" \
            "http://localhost:8001/api/v1/entities/$ENTITY_ID")
        HANDLE_COUNT=$(echo "$GET_ENTITY_RESPONSE" | jq -r '.handles | length' 2>/dev/null || echo "0")
        ATTR_COUNT=$(echo "$GET_ENTITY_RESPONSE" | jq -r '.attributes | length' 2>/dev/null || echo "0")

        if [ "$HANDLE_COUNT" -gt 0 ] && [ "$ATTR_COUNT" -gt 0 ]; then
            info "  ✓ Entity detail: $HANDLE_COUNT handle(s), $ATTR_COUNT attribute(s)"
        else
            warn "  ✗ Entity detail incomplete (handles=$HANDLE_COUNT, attrs=$ATTR_COUNT)"
        fi

        # 9c. Add a second handle
        ADD_HANDLE_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST \
            -H "Authorization: Bearer $ACCESS_TOKEN" \
            -H "Content-Type: application/json" \
            "http://localhost:8001/api/v1/entities/$ENTITY_ID/handles" \
            -d '{"handle_type": "teams_id", "handle_value": "alice@example.onmicrosoft.com"}')
        ADD_HTTP_CODE=$(echo "$ADD_HANDLE_RESPONSE" | tail -1)
        ADD_BODY=$(echo "$ADD_HANDLE_RESPONSE" | sed '$d')
        HANDLE_ID=$(echo "$ADD_BODY" | jq -r '.id // empty' 2>/dev/null)

        if [ -n "$HANDLE_ID" ] && [ "$HANDLE_ID" != "null" ]; then
            info "  ✓ Second handle added: id=$HANDLE_ID"
        elif [ "$ADD_HTTP_CODE" = "409" ]; then
            info "  ✓ Second handle already exists (re-run)"
        else
            warn "  ✗ Add handle failed (response: $ADD_BODY)"
        fi

        # 9d. List entities
        LIST_RESPONSE=$(curl -s -H "Authorization: Bearer $ACCESS_TOKEN" \
            "http://localhost:8001/api/v1/entities?search=Alice")
        LIST_TOTAL=$(echo "$LIST_RESPONSE" | jq -r '.total // 0' 2>/dev/null || echo "0")

        if [ "$LIST_TOTAL" -gt 0 ]; then
            info "  ✓ Entity list: found $LIST_TOTAL entity(s) matching 'Alice'"
            ENTITY_OK=1
        else
            warn "  ✗ Entity not found in list (response: $LIST_RESPONSE)"
        fi
    fi

    kill $PF_UI4_PID 2>/dev/null || true
else
    warn "  ⊘ Skipped — Stage 6 (login) did not pass"
fi

# Stage 10: Batch alert generation
info "Batch alert generation via API (Stage 10)..."
GENERATION_OK=0

if [ "$LOGIN_OK" -eq 1 ] && [ "$ALERT_OK" -eq 1 ]; then
    kubectl port-forward -n umbrella-ui svc/umbrella-ui-backend 8001:8000 >/dev/null 2>&1 &
    PF_UI5_PID=$!
    sleep 3

    # Delete any existing alerts for the compliance rule so the generator creates them fresh
    kubectl exec -n umbrella-storage "$PG_POD" -- \
      psql -U postgres -d umbrella -c \
      "DELETE FROM alert.alerts WHERE rule_id = 'cccccccc-0000-0000-0000-000000000002';" 2>/dev/null

    # Create a generation job scoped to the test document only
    JOB_RESPONSE=$(curl -s -X POST \
        -H "Authorization: Bearer $ACCESS_TOKEN" \
        -H "Content-Type: application/json" \
        "http://localhost:8001/api/v1/alert-generation/jobs" \
        -d '{"scope_type":"all","query_kql":"message_id:pipeline-test-001"}')
    JOB_ID=$(echo "$JOB_RESPONSE" | jq -r '.id // empty' 2>/dev/null)
    JOB_STATUS=$(echo "$JOB_RESPONSE" | jq -r '.status // empty' 2>/dev/null)

    if [ -n "$JOB_ID" ] && [ "$JOB_ID" != "null" ]; then
        info "  ✓ Generation job created: id=$JOB_ID status=$JOB_STATUS"
    else
        warn "  ✗ Generation job creation failed (response: $JOB_RESPONSE)"
    fi

    # Poll until the job completes (max 60s)
    if [ -n "$JOB_ID" ] && [ "$JOB_ID" != "null" ]; then
        for attempt in $(seq 1 12); do
            sleep 5
            POLL_RESPONSE=$(curl -s -H "Authorization: Bearer $ACCESS_TOKEN" \
                "http://localhost:8001/api/v1/alert-generation/jobs/$JOB_ID")
            JOB_STATUS=$(echo "$POLL_RESPONSE" | jq -r '.status // empty' 2>/dev/null)
            ALERTS_CREATED=$(echo "$POLL_RESPONSE" | jq -r '.alerts_created // 0' 2>/dev/null)
            RULES_EVALUATED=$(echo "$POLL_RESPONSE" | jq -r '.rules_evaluated // 0' 2>/dev/null)
            DOCS_SCANNED=$(echo "$POLL_RESPONSE" | jq -r '.documents_scanned // 0' 2>/dev/null)
            ERROR_MSG=$(echo "$POLL_RESPONSE" | jq -r '.error_message // empty' 2>/dev/null)

            if [ "$JOB_STATUS" = "completed" ] || [ "$JOB_STATUS" = "failed" ]; then
                break
            fi
            echo -ne "\r  Job status: $JOB_STATUS (attempt $attempt/12)..."
        done
        echo ""

        if [ "$JOB_STATUS" = "completed" ]; then
            info "  ✓ Job completed: rules_evaluated=$RULES_EVALUATED docs_scanned=$DOCS_SCANNED alerts_created=$ALERTS_CREATED"
            if [ "$ALERTS_CREATED" -gt 0 ]; then
                info "  ✓ Batch generation created $ALERTS_CREATED alert(s)"
                GENERATION_OK=1
            else
                warn "  ✗ Job completed but created 0 alerts (expected at least 1 for 'Compliance Keyword Match' rule)"
                warn "  Backend logs (last 30 lines):"
                kubectl logs -n umbrella-ui -l app=umbrella-ui-backend --tail=30 2>/dev/null || true
            fi
        else
            warn "  ✗ Job ended with status=$JOB_STATUS error=$ERROR_MSG"
            warn "  Backend logs (last 30 lines):"
            kubectl logs -n umbrella-ui -l app=umbrella-ui-backend --tail=30 2>/dev/null || true
        fi
    fi

    kill $PF_UI5_PID 2>/dev/null || true
else
    warn "  ⊘ Skipped — Stage 6 (login) or Stage 7 (alert) did not pass"
fi

# ─── Summary ──────────────────────────────────────────────────────────────────
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
echo "Stage 8 (Alert review E2E):  $([ "$REVIEW_OK" -eq 1 ]        && echo '[✓ PASS]' || echo '[✗ FAIL]')"
echo "Stage 9 (Entity resolution): $([ "$ENTITY_OK" -eq 1 ]        && echo '[✓ PASS]' || echo '[✗ FAIL]')"
echo "Stage 10 (Alert generation): $([ "$GENERATION_OK" -eq 1 ]    && echo '[✓ PASS]' || echo '[✗ FAIL]')"
echo "=========================================="
echo ""

if [ "$RAW_COUNT" -gt 0 ] && [ "$PARSED_COUNT" -gt 0 ] && \
   [ "$NORMALIZED_COUNT" -gt 0 ] && [ "$ES_RESULT" -gt 0 ] && \
   [ "$UI_RESULT" -gt 0 ] && [ "$LOGIN_OK" -eq 1 ] && [ "$ALERT_OK" -eq 1 ] && \
   [ "$REVIEW_OK" -eq 1 ] && [ "$ENTITY_OK" -eq 1 ] && [ "$GENERATION_OK" -eq 1 ]; then
    info "✓ PIPELINE TEST PASSED - All 10 stages working!"
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
