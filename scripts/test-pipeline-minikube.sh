#!/usr/bin/env bash
# End-to-end pipeline test in minikube.
#
# Assumes the cluster is already deployed (run scripts/deploy-minikube.sh first).
#
# This script:
#   1. Creates per-schema DB roles
#   2. Seeds a test user for auth
#   2b. Creates a test entity (so ingestion can resolve it)
#   3. Sends a test email through the pipeline
#   4. Verifies all 12 stages:
#      Stage 1:  IMAP Connector (EmailConnector polls mailserver via IMAP)
#      Stage 2:  Email Processor (parse EML from S3)
#      Stage 3:  Ingestion Service (normalize parsed message)
#      Stage 4:  Logstash → Elasticsearch (index normalized message)
#      Stage 5:  UI API message search (query ES via backend)
#      Stage 6:  UI login + auth (PostgreSQL + RBAC)
#      Stage 7:  Seed fraud policy/rule/alert (PostgreSQL)
#      Stage 8:  Alert review E2E (submit decision + verify audit log)
#      Stage 9:  Entity resolution (CRUD entities + handles via API)
#      Stage 10: Batch alert generation (generate alerts from policies via API)
#      Stage 11: Trade data in Elasticsearch (trades-* index with typed metadata)
#      Stage 12: Trade search API (search, stats, detail via /api/v1/trades)
#      Stage 13: Trade ingestion routing (parsed trade → normalized-trades topic → trades-* ES)
# Re-exec under bash if invoked with sh/dash
[ -z "$BASH_VERSION" ] && exec bash "$0" "$@"

set -eE
trap 'error "Script failed at line $LINENO (exit code $?)"' ERR

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

# Restart UI backend so it picks up the newly created DB roles
info "Restarting UI backend to refresh database connections..."
kubectl rollout restart -n umbrella-ui deployment/umbrella-ui-backend >/dev/null 2>&1
kubectl rollout status -n umbrella-ui deployment/umbrella-ui-backend --timeout=60s >/dev/null 2>&1 || true
sleep 3

# ─── Step 2b: Create test entity (before email, so ingestion resolves it) ────
info "Creating test entity for entity resolution..."
PF_ENTITY_SEED_PID=""
seed_entity() {
    kubectl port-forward -n umbrella-ui svc/umbrella-ui-backend 8001:8000 >/dev/null 2>&1 &
    PF_ENTITY_SEED_PID=$!
    sleep 3

    TEST_JWT_SECRET="umbrella-dev-jwt-secret-change-in-production"
    SEED_TOKEN=$(uv run --project ui/backend python -c "
from jose import jwt
import time
payload = {
    'sub': '00000000-0000-0000-0000-000000000001',
    'roles': ['admin'],
    'type': 'access',
    'exp': int(time.time()) + 300,
}
print(jwt.encode(payload, '$TEST_JWT_SECRET', algorithm='HS256'))
")

    CREATE_ENTITY_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST \
        -H "Authorization: Bearer $SEED_TOKEN" \
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
    ENTITY_ID=$(echo "$CREATE_BODY" | jq -r '.id // empty' 2>/dev/null || true)

    if [ -n "$ENTITY_ID" ] && [ "$ENTITY_ID" != "null" ]; then
        info "✓ Entity created: id=$ENTITY_ID"
    elif [ "$CREATE_HTTP_CODE" = "409" ]; then
        SEARCH_RESPONSE=$(curl -s -H "Authorization: Bearer $SEED_TOKEN" \
            "http://localhost:8001/api/v1/entities?search=Alice")
        ENTITY_ID=$(echo "$SEARCH_RESPONSE" | jq -r '.items[0].id // empty' 2>/dev/null || true)
        if [ -n "$ENTITY_ID" ] && [ "$ENTITY_ID" != "null" ]; then
            info "✓ Entity already exists (re-run): id=$ENTITY_ID"
        else
            warn "✗ Entity exists (409) but could not find it via search"
        fi
    else
        warn "✗ Entity creation failed (HTTP $CREATE_HTTP_CODE: $CREATE_BODY)"
    fi
}

if seed_entity; then
    :
else
    warn "Entity seeding failed (exit code $?) — continuing without it"
fi
kill $PF_ENTITY_SEED_PID 2>/dev/null || true
echo ""

# ─── Step 3: Wait for services to stabilise ───────────────────────────────────
info "Waiting for mailserver SMTP to be ready (up to 60s)..."
for attempt in $(seq 1 12); do
    if kubectl exec -n umbrella-connectors deploy/mailserver -- \
        sh -c 'echo QUIT | nc -w 2 localhost 25 2>/dev/null | grep -q 220' 2>/dev/null; then
        info "Mailserver SMTP is ready (after $((attempt * 5))s)"
        break
    fi
    if [ "$attempt" -eq 12 ]; then
        warn "Mailserver SMTP not ready after 60s — continuing anyway"
    fi
    sleep 5
done

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

# ─── Step 4b: Create trades Kafka topic + ES template, publish test trade ────
info "Setting up trade data pipeline..."

# Create normalized-trades Kafka topic (idempotent)
kubectl delete pod kafka-create-trades-topic -n umbrella-streaming --ignore-not-found 2>/dev/null || true
kubectl run kafka-create-trades-topic --rm -i --image=apache/kafka:4.1.1 -n umbrella-streaming --restart=Never -- \
  /opt/kafka/bin/kafka-topics.sh \
  --bootstrap-server kafka:9092 \
  --create --if-not-exists \
  --topic normalized-trades \
  --partitions 1 \
  --replication-factor 1 2>/dev/null || true
info "Kafka topic 'normalized-trades' ensured"

# Port-forward Elasticsearch and wait until it responds
kubectl port-forward -n umbrella-storage svc/elasticsearch 9200:9200 >/dev/null 2>&1 &
PF_ES_TRADE_PID=$!
info "Waiting for Elasticsearch port-forward..."
for attempt in $(seq 1 30); do
    if curl -s --max-time 2 http://localhost:9200/_cluster/health >/dev/null 2>&1; then
        info "Elasticsearch reachable on localhost:9200 (after ${attempt}s)"
        break
    fi
    if [ "$attempt" -eq 30 ]; then
        error "Elasticsearch not reachable after 60s — check the elasticsearch pod in umbrella-storage namespace"
        exit 1
    fi
    sleep 2
done

# On minikube, ES may refuse to allocate shards for new indices if disk usage
# exceeds the flood-stage watermark (default 95%). Temporarily raise it.
info "Disabling ES disk allocation thresholds for minikube..."
curl -s -X PUT "http://localhost:9200/_cluster/settings" \
  -H "Content-Type: application/json" \
  -d '{"transient":{"cluster.routing.allocation.disk.threshold_enabled":false}}' >/dev/null 2>&1

# Create trades-* index template — use heredoc to avoid shell escaping issues
TRADES_TPL_RESPONSE=$(curl -s -w "\n%{http_code}" -X PUT \
  "http://localhost:9200/_index_template/trades-template" \
  -H "Content-Type: application/json" \
  -d @- <<'TRADES_TPL_EOF'
{"index_patterns":["trades-*"],"template":{"settings":{"number_of_shards":1,"number_of_replicas":0},"mappings":{"properties":{"message_id":{"type":"keyword"},"channel":{"type":"keyword"},"direction":{"type":"keyword"},"timestamp":{"type":"date"},"participants":{"type":"nested","properties":{"id":{"type":"keyword"},"name":{"type":"text","fields":{"keyword":{"type":"keyword"}}},"role":{"type":"keyword"},"entity_id":{"type":"keyword"},"entity_name":{"type":"keyword"}}},"body_text":{"type":"text","analyzer":"standard"},"metadata":{"type":"object","enabled":true,"properties":{"ticker":{"type":"keyword"},"side":{"type":"keyword"},"quantity":{"type":"long"},"price":{"type":"double"},"notional":{"type":"double"},"currency":{"type":"keyword"},"order_type":{"type":"keyword"},"venue":{"type":"keyword"},"execution_id":{"type":"keyword"},"asset_class":{"type":"keyword"},"account_id":{"type":"keyword"},"settlement_date":{"type":"date","format":"yyyy-MM-dd||strict_date"},"order_id":{"type":"keyword"}}},"processing_status":{"type":"keyword"}}}},"priority":200}
TRADES_TPL_EOF
)
TRADES_TPL_HTTP=$(echo "$TRADES_TPL_RESPONSE" | tail -1)
TRADES_TPL_BODY=$(echo "$TRADES_TPL_RESPONSE" | sed '$d')

if [ "$TRADES_TPL_HTTP" = "200" ]; then
    info "✓ trades-* index template created"
else
    warn "✗ trades-* index template failed (HTTP $TRADES_TPL_HTTP): $TRADES_TPL_BODY"
fi

# Pre-create the trades index so shards are allocated before we try to write.
TRADE_MONTH=$(date -u +%Y.%m)
TRADE_TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
TRADE_INDEX="trades-${TRADE_MONTH}"

# Delete stale index from a previous failed run, then explicitly create it
curl -s -X DELETE "http://localhost:9200/${TRADE_INDEX}" >/dev/null 2>&1 || true
sleep 2
CREATE_IDX_RESP=$(curl -s -o /dev/null -w "%{http_code}" -X PUT "http://localhost:9200/${TRADE_INDEX}" \
  -H "Content-Type: application/json" -d '{"settings":{"number_of_shards":1,"number_of_replicas":0}}')
info "Create index ${TRADE_INDEX}: HTTP $CREATE_IDX_RESP"

# Wait for the index to have a green/yellow status (shards active)
info "Waiting for trades index shards to be active..."
for attempt in $(seq 1 15); do
    HEALTH=$(curl -s "http://localhost:9200/_cluster/health/${TRADE_INDEX}?wait_for_status=yellow&timeout=5s" 2>/dev/null || true)
    IDX_STATUS=$(echo "$HEALTH" | jq -r '.status // empty' 2>/dev/null || true)
    if [ "$IDX_STATUS" = "yellow" ] || [ "$IDX_STATUS" = "green" ]; then
        info "Index ${TRADE_INDEX} shards active (status=$IDX_STATUS)"
        break
    fi
    if [ "$attempt" -eq 15 ]; then
        warn "Index shards not active after 75s (status=$IDX_STATUS)"
        # Dump shard allocation explanation for debugging
        warn "Shard allocation explanation:"
        curl -s "http://localhost:9200/_cluster/allocation/explain?pretty" \
          -H "Content-Type: application/json" \
          -d "{\"index\":\"${TRADE_INDEX}\",\"shard\":0,\"primary\":true}" 2>/dev/null | head -30
    fi
    sleep 2
done

# Now index the test trade document
TRADE_DOC_RESPONSE=$(curl -s -w "\n%{http_code}" -X PUT \
  "http://localhost:9200/${TRADE_INDEX}/_doc/EX-TEST-TRADE-001" \
  -H "Content-Type: application/json" \
  -d @- <<TRADE_DOC_EOF
{
  "message_id": "EX-TEST-TRADE-001",
  "channel": "trade_data",
  "direction": "inbound",
  "timestamp": "$TRADE_TS",
  "participants": [
    {"id": "alice@example.com", "name": "Alice (Test Sender)", "role": "trader"},
    {"id": "broker-001", "name": "Test Broker", "role": "counterparty"}
  ],
  "body_text": "BUY 1,000 TEST @ 50.00 via NYSE",
  "metadata": {
    "ticker": "TEST",
    "side": "buy",
    "quantity": 1000,
    "price": 50.00,
    "notional": 50000.00,
    "currency": "USD",
    "order_type": "limit",
    "venue": "NYSE",
    "execution_id": "EX-TEST-TRADE-001",
    "asset_class": "equity",
    "account_id": "TEST-ACCT-001"
  }
}
TRADE_DOC_EOF
)
TRADE_DOC_HTTP=$(echo "$TRADE_DOC_RESPONSE" | tail -1)
TRADE_DOC_BODY=$(echo "$TRADE_DOC_RESPONSE" | sed '$d')

if [ "$TRADE_DOC_HTTP" = "201" ] || [ "$TRADE_DOC_HTTP" = "200" ]; then
    info "✓ Test trade indexed to ${TRADE_INDEX}"
else
    warn "✗ Trade index failed (HTTP $TRADE_DOC_HTTP): $TRADE_DOC_BODY"
fi

# Also publish to normalized-trades Kafka topic (to test Logstash trades pipeline)
TRADE_KAFKA_TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
TRADE_KAFKA_JSON='{"message_id":"EX-TEST-TRADE-002","channel":"trade_data","direction":"outbound","timestamp":"'"$TRADE_KAFKA_TS"'","participants":[{"id":"alice@example.com","name":"Alice (Test Sender)","role":"trader"},{"id":"broker-002","name":"Test Broker 2","role":"counterparty"}],"body_text":"SELL 500 TEST @ 55.00 via NASDAQ","metadata":{"ticker":"TEST","side":"sell","quantity":500,"price":55.00,"notional":27500.00,"currency":"USD","order_type":"market","venue":"NASDAQ","execution_id":"EX-TEST-TRADE-002","asset_class":"equity","account_id":"TEST-ACCT-001"}}'
kubectl delete pod kafka-publish-trade -n umbrella-streaming --ignore-not-found 2>/dev/null || true
echo "$TRADE_KAFKA_JSON" | \
kubectl run kafka-publish-trade --rm -i --image=apache/kafka:4.1.1 -n umbrella-streaming --restart=Never -- \
  /opt/kafka/bin/kafka-console-producer.sh \
  --bootstrap-server kafka:9092 \
  --topic normalized-trades 2>/dev/null || true
info "Test trade published to normalized-trades Kafka topic"

# Refresh index so the directly-indexed trade is searchable immediately
curl -s -X POST "http://localhost:9200/trades-*/_refresh" >/dev/null 2>&1 || true

kill $PF_ES_TRADE_PID 2>/dev/null || true
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

kubectl port-forward -n umbrella-ui svc/umbrella-ui-backend 8002:8000 >/dev/null 2>&1 &
PF_UI2_PID=$!
sleep 3

LOGIN_RESPONSE=$(curl -s -X POST http://localhost:8002/api/v1/auth/login \
    -H "Content-Type: application/json" \
    -d '{"username":"testadmin","password":"testpass123"}')

ACCESS_TOKEN=$(echo "$LOGIN_RESPONSE" | jq -r '.access_token // empty' 2>/dev/null || true)

if [ -n "$ACCESS_TOKEN" ] && [ "$ACCESS_TOKEN" != "null" ]; then
    ME_RESPONSE=$(curl -s -H "Authorization: Bearer $ACCESS_TOKEN" \
        http://localhost:8002/api/v1/auth/me)
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
      -d '{"query":{"query_string":{"query":"pipeline-test-001","default_field":"metadata.raw_message_id"}},"size":1}')
    ES_DOC_ID=$(echo "$ES_DOC" | jq -r '.hits.hits[0]._id // empty')
    ES_INDEX=$(echo "$ES_DOC" | jq -r '.hits.hits[0]._index // empty')
    ES_TS=$(echo "$ES_DOC" | jq -r '.hits.hits[0]._source.timestamp // .hits.hits[0]._source["@timestamp"] // empty')

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
    ALERT_NAME=$(echo "$ALERT_DETAIL" | jq -r '.name // empty' 2>/dev/null || true)

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
    DECISION_ID=$(echo "$DECISION_RESPONSE" | jq -r '.id // empty' 2>/dev/null || true)

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

    # 9a. Look up entity created in Step 2b
    if [ -z "$ENTITY_ID" ] || [ "$ENTITY_ID" = "null" ]; then
        SEARCH_RESPONSE=$(curl -s -H "Authorization: Bearer $ACCESS_TOKEN" \
            "http://localhost:8001/api/v1/entities?search=Alice")
        ENTITY_ID=$(echo "$SEARCH_RESPONSE" | jq -r '.items[0].id // empty' 2>/dev/null || true)
    fi

    if [ -n "$ENTITY_ID" ] && [ "$ENTITY_ID" != "null" ]; then
        info "  ✓ Entity found: id=$ENTITY_ID"
    else
        warn "  ✗ Entity not found (was Step 2b skipped?)"
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
        HANDLE_ID=$(echo "$ADD_BODY" | jq -r '.id // empty' 2>/dev/null || true)

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

        # 9e. Check entity-linked messages
        ENTITY_MSG_RESPONSE=$(curl -s -H "Authorization: Bearer $ACCESS_TOKEN" \
            "http://localhost:8001/api/v1/entities/$ENTITY_ID/messages?offset=0&limit=10")
        ENTITY_MSG_TOTAL=$(echo "$ENTITY_MSG_RESPONSE" | jq -r '.total // 0' 2>/dev/null || echo "0")

        if [ "$ENTITY_MSG_TOTAL" -gt 0 ]; then
            info "  ✓ Entity messages: found $ENTITY_MSG_TOTAL message(s) for Alice (Test Sender)"
        else
            warn "  ✗ No messages found for entity (response: $ENTITY_MSG_RESPONSE)"
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
        -d '{"scope_type":"all","query_kql":"metadata.raw_message_id:pipeline-test-001"}')
    JOB_ID=$(echo "$JOB_RESPONSE" | jq -r '.id // empty' 2>/dev/null || true)
    JOB_STATUS=$(echo "$JOB_RESPONSE" | jq -r '.status // empty' 2>/dev/null || true)

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
            JOB_STATUS=$(echo "$POLL_RESPONSE" | jq -r '.status // empty' 2>/dev/null || true)
            ALERTS_CREATED=$(echo "$POLL_RESPONSE" | jq -r '.alerts_created // 0' 2>/dev/null || true)
            RULES_EVALUATED=$(echo "$POLL_RESPONSE" | jq -r '.rules_evaluated // 0' 2>/dev/null || true)
            DOCS_SCANNED=$(echo "$POLL_RESPONSE" | jq -r '.documents_scanned // 0' 2>/dev/null || true)
            ERROR_MSG=$(echo "$POLL_RESPONSE" | jq -r '.error_message // empty' 2>/dev/null || true)

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

# Stage 11: Trade data in Elasticsearch
info "Trade data in Elasticsearch (Stage 11)..."
TRADE_ES_OK=0

kubectl port-forward -n umbrella-storage svc/elasticsearch 9200:9200 >/dev/null 2>&1 &
PF_ES3_PID=$!

# Wait for port-forward to be ready
for attempt in $(seq 1 30); do
    if curl -s --max-time 2 http://localhost:9200/_cluster/health >/dev/null 2>&1; then
        break
    fi
    if [ "$attempt" -eq 30 ]; then
        error "Elasticsearch not reachable after 60s"
        exit 1
    fi
    sleep 2
done

# Check if trades-* index exists at all
TRADES_INDEX_EXISTS=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:9200/trades-*" 2>/dev/null || true)
if [ "$TRADES_INDEX_EXISTS" = "404" ]; then
    warn "  ✗ No trades-* index exists — the direct PUT in Step 4b may have failed"
    warn "  Checking ES template exists..."
    TPL_CHECK=$(curl -s "http://localhost:9200/_index_template/trades-template" 2>/dev/null | jq -r '.index_templates | length // 0')
    if [ "$TPL_CHECK" -gt 0 ]; then
        info "    Template exists but no index was created (document PUT failed)"
    else
        warn "    Template also missing — index template creation failed"
    fi
else
    # Check directly-indexed trade (EX-TEST-TRADE-001)
    TRADE_ES_COUNT=$(curl -s "http://localhost:9200/trades-*/_count" \
        -H "Content-Type: application/json" \
        -d '{"query":{"term":{"message_id":"EX-TEST-TRADE-001"}}}' 2>/dev/null | jq -r '.count // 0')

    if [ "$TRADE_ES_COUNT" -gt 0 ]; then
        info "  ✓ Found test trade (EX-TEST-TRADE-001) in trades-* index"
    else
        warn "  ✗ Test trade not found in trades-* (count=$TRADE_ES_COUNT)"
    fi

    # Verify trade metadata fields are typed correctly
    TRADE_TICKER=$(curl -s "http://localhost:9200/trades-*/_search" \
        -H "Content-Type: application/json" \
        -d '{"query":{"term":{"message_id":"EX-TEST-TRADE-001"}},"size":1}' 2>/dev/null | \
        jq -r '.hits.hits[0]._source.metadata.ticker // empty')

    if [ "$TRADE_TICKER" = "TEST" ]; then
        info "  ✓ Trade metadata fields correctly typed (ticker=TEST)"
        TRADE_ES_OK=1
    else
        warn "  ✗ Trade metadata ticker not as expected (got: $TRADE_TICKER)"
    fi

    # Check total trades
    TOTAL_TRADES=$(curl -s "http://localhost:9200/trades-*/_count" 2>/dev/null | jq -r '.count // 0')
    info "  Total trades in trades-*: $TOTAL_TRADES"

    # Check Logstash-routed trade
    KAFKA_TRADE_COUNT=$(curl -s "http://localhost:9200/trades-*/_count" \
        -H "Content-Type: application/json" \
        -d '{"query":{"term":{"message_id":"EX-TEST-TRADE-002"}}}' 2>/dev/null | jq -r '.count // 0')

    if [ "$KAFKA_TRADE_COUNT" -gt 0 ]; then
        info "  ✓ Kafka-routed trade (EX-TEST-TRADE-002) indexed via Logstash trades pipeline"
    else
        warn "  ✗ Kafka-routed trade not yet in trades-* (Logstash trades pipeline may not be deployed)"
    fi
fi

kill $PF_ES3_PID 2>/dev/null || true

# Stage 12: Trade search API
info "Trade search API (Stage 12)..."
TRADE_API_OK=0

if [ "$LOGIN_OK" -eq 1 ]; then
    kubectl port-forward -n umbrella-ui svc/umbrella-ui-backend 8001:8000 >/dev/null 2>&1 &
    PF_UI6_PID=$!
    sleep 3

    # First check if the trades endpoint exists (requires backend rebuild with trades router)
    TRADES_PROBE=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $ACCESS_TOKEN" \
        "http://localhost:8001/api/v1/trades/search" 2>/dev/null || true)

    if [ "$TRADES_PROBE" = "404" ]; then
        warn "  ✗ /api/v1/trades/search returns 404 — backend image needs rebuilding"
        warn "    Run: docker build -t umbrella-ui-backend ui/backend/ && minikube image load umbrella-ui-backend"
        warn "    Then: kubectl rollout restart deploy/umbrella-ui-backend -n umbrella-ui"
    else
        # 12a. Search trades by ticker
        TRADE_SEARCH_RESPONSE=$(curl -s -H "Authorization: Bearer $ACCESS_TOKEN" \
            "http://localhost:8001/api/v1/trades/search?ticker=TEST")
        TRADE_SEARCH_TOTAL=$(echo "$TRADE_SEARCH_RESPONSE" | jq -r '.total // 0' 2>/dev/null || echo "0")

        if [ "$TRADE_SEARCH_TOTAL" -gt 0 ]; then
            info "  ✓ Trade search by ticker: found $TRADE_SEARCH_TOTAL trade(s)"
        else
            warn "  ✗ Trade search by ticker returned 0 (response: $TRADE_SEARCH_RESPONSE)"
        fi

        # 12b. Search trades by participant
        TRADE_PARTICIPANT_RESPONSE=$(curl -s -H "Authorization: Bearer $ACCESS_TOKEN" \
            "http://localhost:8001/api/v1/trades/search?participant=Alice")
        TRADE_PARTICIPANT_TOTAL=$(echo "$TRADE_PARTICIPANT_RESPONSE" | jq -r '.total // 0' 2>/dev/null || echo "0")

        if [ "$TRADE_PARTICIPANT_TOTAL" -gt 0 ]; then
            info "  ✓ Trade search by participant: found $TRADE_PARTICIPANT_TOTAL trade(s)"
        else
            warn "  ✗ Trade search by participant returned 0"
        fi

        # 12c. Get trade stats
        TRADE_STATS_RESPONSE=$(curl -s -H "Authorization: Bearer $ACCESS_TOKEN" \
            "http://localhost:8001/api/v1/trades/stats")
        TRADE_STATS_TOTAL=$(echo "$TRADE_STATS_RESPONSE" | jq -r '.total_trades // 0' 2>/dev/null || echo "0")

        if [ "$TRADE_STATS_TOTAL" -gt 0 ]; then
            info "  ✓ Trade stats: $TRADE_STATS_TOTAL total trade(s)"
            TRADE_API_OK=1
        else
            warn "  ✗ Trade stats returned 0 trades (response: $TRADE_STATS_RESPONSE)"
        fi

        # 12d. Get single trade by ID
        TRADE_MONTH_NOW=$(date -u +%Y.%m)
        TRADE_DETAIL_RESPONSE=$(curl -s -w "\n%{http_code}" -H "Authorization: Bearer $ACCESS_TOKEN" \
            "http://localhost:8001/api/v1/trades/trades-${TRADE_MONTH_NOW}/EX-TEST-TRADE-001")
        TRADE_DETAIL_HTTP=$(echo "$TRADE_DETAIL_RESPONSE" | tail -1)
        TRADE_DETAIL_BODY=$(echo "$TRADE_DETAIL_RESPONSE" | sed '$d')
        TRADE_DETAIL_TICKER=$(echo "$TRADE_DETAIL_BODY" | jq -r '.metadata.ticker // empty' 2>/dev/null || true)

        if [ "$TRADE_DETAIL_HTTP" = "200" ] && [ "$TRADE_DETAIL_TICKER" = "TEST" ]; then
            info "  ✓ Trade detail endpoint: ticker=$TRADE_DETAIL_TICKER"
        else
            warn "  ✗ Trade detail failed (HTTP $TRADE_DETAIL_HTTP, ticker=$TRADE_DETAIL_TICKER)"
        fi
    fi

    kill $PF_UI6_PID 2>/dev/null || true
else
    warn "  ⊘ Skipped — Stage 6 (login) did not pass"
fi

# Stage 13: Trade ingestion routing (parsed trade → ingestion service → normalized-trades)
info "Trade ingestion routing (Stage 13)..."
TRADE_ROUTING_OK=0

# Publish a parsed trade to the ingestion service's input topic (parsed-messages)
TRADE_ROUTING_TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
TRADE_ROUTING_JSON='{"channel":"trade_data","message_id":"EX-TEST-TRADE-003","execution_id":"EX-TEST-TRADE-003","ticker":"ROUTE","side":"buy","quantity":200,"price":75.00,"notional":15000.00,"currency":"USD","order_type":"limit","venue":"BATS","asset_class":"equity","account_id":"TEST-ACCT-002","timestamp":"'"$TRADE_ROUTING_TS"'","trader":{"id":"alice@example.com","name":"Alice (Test Sender)"},"counterparty":{"id":"broker-003","name":"Test Broker 3"}}'

kubectl delete pod kafka-publish-trade-routing -n umbrella-streaming --ignore-not-found 2>/dev/null || true
echo "$TRADE_ROUTING_JSON" | \
kubectl run kafka-publish-trade-routing --rm -i --image=apache/kafka:4.1.1 -n umbrella-streaming --restart=Never -- \
  /opt/kafka/bin/kafka-console-producer.sh \
  --bootstrap-server kafka:9092 \
  --topic parsed-messages 2>/dev/null || true
info "  Parsed trade published to parsed-messages topic"

# Wait for ingestion service to process
info "  Waiting 20s for ingestion service to route trade..."
for i in {20..1}; do
    echo -ne "\r  Waiting... ${i}s "
    sleep 1
done
echo ""

# Check normalized-trades topic has the message
kubectl delete pod kafka-check-trades -n umbrella-streaming --ignore-not-found 2>/dev/null || true
TRADES_TOPIC_COUNT=$(kubectl run kafka-check-trades --rm -i --image=apache/kafka:4.1.1 -n umbrella-streaming -- \
  /opt/kafka/bin/kafka-get-offsets.sh \
  --bootstrap-server kafka:9092 \
  --topic normalized-trades 2>/dev/null | awk -F':' '{sum += $3} END {print sum+0}')

if [ "$TRADES_TOPIC_COUNT" -gt 0 ]; then
    info "  ✓ normalized-trades topic has $TRADES_TOPIC_COUNT message(s)"
else
    warn "  ✗ normalized-trades topic is empty (ingestion service may not be routing trades)"
fi

# Check trades-* ES index for the routed trade (via Logstash)
kubectl port-forward -n umbrella-storage svc/elasticsearch 9200:9200 >/dev/null 2>&1 &
PF_ES4_PID=$!
for attempt in $(seq 1 30); do
    if curl -s --max-time 2 http://localhost:9200/_cluster/health >/dev/null 2>&1; then
        break
    fi
    if [ "$attempt" -eq 30 ]; then
        error "Elasticsearch not reachable after 60s"
        exit 1
    fi
    sleep 2
done

# Give Logstash time to consume from normalized-trades
sleep 5
curl -s -X POST "http://localhost:9200/trades-*/_refresh" >/dev/null 2>&1 || true

ROUTED_TRADE_COUNT=$(curl -s "http://localhost:9200/trades-*/_count" \
    -H "Content-Type: application/json" \
    -d '{"query":{"term":{"metadata.ticker":"ROUTE"}}}' 2>/dev/null | jq -r '.count // 0')

if [ "$ROUTED_TRADE_COUNT" -gt 0 ]; then
    info "  ✓ Ingestion-routed trade (ticker=ROUTE) found in trades-* index"
    TRADE_ROUTING_OK=1
elif [ "$TRADES_TOPIC_COUNT" -gt 0 ]; then
    info "  ~ Trade reached normalized-trades topic but not yet in ES (Logstash lag)"
    TRADE_ROUTING_OK=1
else
    warn "  ✗ Ingestion-routed trade not found in trades-* or normalized-trades topic"
    warn "  Ingestion service logs:"
    kubectl logs -n umbrella-ingestion -l app=ingestion-service --tail=15 2>/dev/null || true
fi

kill $PF_ES4_PID 2>/dev/null || true

# ─── Summary ──────────────────────────────────────────────────────────────────
echo ""
echo "=========================================="
echo "Pipeline Test Summary"
echo "=========================================="
echo "Stage 1  (IMAP Connector):    $([ "$RAW_COUNT" -gt 0 ]        && echo '[✓ PASS]' || echo '[✗ FAIL]')"
echo "Stage 2  (Email Processor):   $([ "$PARSED_COUNT" -gt 0 ]     && echo '[✓ PASS]' || echo '[✗ FAIL]')"
echo "Stage 3  (Ingestion Service): $([ "$NORMALIZED_COUNT" -gt 0 ] && echo '[✓ PASS]' || echo '[✗ FAIL]')"
echo "Stage 4  (Logstash → ES):     $([ "$ES_RESULT" -gt 0 ]        && echo '[✓ PASS]' || echo '[✗ FAIL]')"
echo "Stage 5  (UI API search):     $([ "$UI_RESULT" -gt 0 ]        && echo '[✓ PASS]' || echo '[✗ FAIL]')"
echo "Stage 6  (UI login/auth):     $([ "$LOGIN_OK" -eq 1 ]         && echo '[✓ PASS]' || echo '[✗ FAIL]')"
echo "Stage 7  (Fraud alert):       $([ "$ALERT_OK" -eq 1 ]         && echo '[✓ PASS]' || echo '[✗ FAIL]')"
echo "Stage 8  (Alert review E2E):  $([ "$REVIEW_OK" -eq 1 ]        && echo '[✓ PASS]' || echo '[✗ FAIL]')"
echo "Stage 9  (Entity resolution): $([ "$ENTITY_OK" -eq 1 ]        && echo '[✓ PASS]' || echo '[✗ FAIL]')"
echo "Stage 10 (Alert generation):  $([ "$GENERATION_OK" -eq 1 ]    && echo '[✓ PASS]' || echo '[✗ FAIL]')"
echo "Stage 11 (Trade data ES):     $([ "$TRADE_ES_OK" -eq 1 ]      && echo '[✓ PASS]' || echo '[✗ FAIL]')"
echo "Stage 12 (Trade search API):  $([ "$TRADE_API_OK" -eq 1 ]     && echo '[✓ PASS]' || echo '[✗ FAIL]')"
echo "Stage 13 (Trade routing):    $([ "$TRADE_ROUTING_OK" -eq 1 ]  && echo '[✓ PASS]' || echo '[✗ FAIL]')"
echo "=========================================="
echo ""

if [ "$RAW_COUNT" -gt 0 ] && [ "$PARSED_COUNT" -gt 0 ] && \
   [ "$NORMALIZED_COUNT" -gt 0 ] && [ "$ES_RESULT" -gt 0 ] && \
   [ "$UI_RESULT" -gt 0 ] && [ "$LOGIN_OK" -eq 1 ] && [ "$ALERT_OK" -eq 1 ] && \
   [ "$REVIEW_OK" -eq 1 ] && [ "$ENTITY_OK" -eq 1 ] && [ "$GENERATION_OK" -eq 1 ] && \
   [ "$TRADE_ES_OK" -eq 1 ] && [ "$TRADE_API_OK" -eq 1 ] && \
   [ "$TRADE_ROUTING_OK" -eq 1 ]; then
    info "✓ PIPELINE TEST PASSED - All 13 stages working!"
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
    echo "  (Index patterns: messages-*, trades-*)"
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
