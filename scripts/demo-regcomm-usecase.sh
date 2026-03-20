#!/usr/bin/env bash
# Regulatory Communications Monitoring Demo
#
# Seeds a realistic insider-trading scenario (Marcus Webb / Sarah Chen / Meridian Technologies)
# across email, Teams chat, trade data, and phone calls, then verifies alerts fire.
#
# Prerequisites: scripts/deploy-minikube.sh and scripts/test-pipeline-minikube.sh must have
# both run successfully (DB roles, test user, entity schema, Kafka topics, Logstash pipeline).
#
# Re-exec under bash if invoked with sh/dash
[ -z "$BASH_VERSION" ] && exec bash "$0" "$@"

set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

echo "=========================================="
echo "Regulatory Communications Monitoring Demo"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { printf "${GREEN}[INFO]${NC} %s\n" "$1"; }
warn()  { printf "${YELLOW}[WARN]${NC} %s\n" "$1"; }
error() { printf "${RED}[ERROR]${NC} %s\n" "$1"; }
step()  { printf "\n${CYAN}── %s${NC}\n" "$1"; }

# Track port-forward PIDs for cleanup
PF_PIDS=()
cleanup() {
    for pid in "${PF_PIDS[@]}"; do
        kill "$pid" 2>/dev/null || true
    done
}
trap cleanup EXIT

start_port_forward() {
    local ns="$1" svc="$2" local_port="$3" remote_port="$4"
    kubectl port-forward -n "$ns" "svc/$svc" "${local_port}:${remote_port}" >/dev/null 2>&1 &
    PF_PIDS+=($!)
    sleep 3
}

# ─── Step 0: Verify prerequisites ────────────────────────────────────────────
step "Step 0: Verify prerequisites"

for ns in umbrella-storage umbrella-streaming umbrella-connectors umbrella-ui; do
    if ! kubectl get ns "$ns" &>/dev/null; then
        error "Namespace $ns not found. Run scripts/deploy-minikube.sh first."
        exit 1
    fi
done

PG_POD=$(kubectl get pod -n umbrella-storage -l app=postgresql -o jsonpath='{.items[0].metadata.name}')
if [ -z "$PG_POD" ]; then
    error "PostgreSQL pod not found in umbrella-storage."
    exit 1
fi

# Check that test user exists (seeded by test-pipeline-minikube.sh)
USER_EXISTS=$(kubectl exec -n umbrella-storage "$PG_POD" -- \
  psql -U postgres -d umbrella -tAc \
  "SELECT COUNT(*) FROM iam.users WHERE username = 'testadmin';" 2>/dev/null || echo "0")
USER_EXISTS="${USER_EXISTS//[[:space:]]/}"

if [ "$USER_EXISTS" -eq 0 ]; then
    error "Test user 'testadmin' not found. Run scripts/test-pipeline-minikube.sh first."
    exit 1
fi

info "Prerequisites OK"

# JWT generation helper
TEST_JWT_SECRET="umbrella-dev-jwt-secret-change-in-production"
generate_token() {
    local role="${1:-admin}"
    uv run --project ui/backend python -c "
from jose import jwt
import time
payload = {
    'sub': '00000000-0000-0000-0000-000000000001',
    'roles': ['$role'],
    'type': 'access',
    'exp': int(time.time()) + 600,
}
print(jwt.encode(payload, '$TEST_JWT_SECRET', algorithm='HS256'))
"
}

# ─── Step 1: Seed entities via UI API ─────────────────────────────────────────
step "Step 1: Seed entities"

start_port_forward umbrella-ui umbrella-ui-backend 8001 8000
TOKEN=$(generate_token admin)

declare -A ENTITY_IDS

create_entity() {
    local display_name="$1"
    local entity_type="$2"
    local handles_json="$3"
    local attrs_json="$4"

    local response
    response=$(curl -s -w "\n%{http_code}" -X POST \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        "http://localhost:8001/api/v1/entities" \
        -d "{
            \"display_name\": \"$display_name\",
            \"entity_type\": \"$entity_type\",
            \"handles\": $handles_json,
            \"attributes\": $attrs_json
        }")
    local http_code
    http_code=$(echo "$response" | tail -1)
    local body
    body=$(echo "$response" | sed '$d')
    local entity_id
    entity_id=$(echo "$body" | jq -r '.id // empty' 2>/dev/null)

    if [ -n "$entity_id" ] && [ "$entity_id" != "null" ]; then
        info "  Created entity: $display_name (id=$entity_id)"
        ENTITY_IDS["$display_name"]="$entity_id"
    elif [ "$http_code" = "409" ]; then
        # Already exists — look it up
        local search_name
        search_name=$(echo "$display_name" | awk '{print $1}')
        local search_resp
        search_resp=$(curl -s -H "Authorization: Bearer $TOKEN" \
            "http://localhost:8001/api/v1/entities?search=$search_name")
        entity_id=$(echo "$search_resp" | jq -r ".items[] | select(.display_name == \"$display_name\") | .id" 2>/dev/null | head -1)
        if [ -n "$entity_id" ] && [ "$entity_id" != "null" ]; then
            info "  Entity exists: $display_name (id=$entity_id)"
            ENTITY_IDS["$display_name"]="$entity_id"
        else
            warn "  Entity exists (409) but could not look up: $display_name"
        fi
    else
        warn "  Failed to create entity: $display_name (HTTP $http_code: $body)"
    fi
}

create_entity "Marcus Webb" "person" \
    '[{"handle_type":"email","handle_value":"marcus.webb@acme-capital.com","is_primary":true},{"handle_type":"teams_id","handle_value":"mwebb@teams.acme-capital.com"},{"handle_type":"email","handle_value":"marcus.personal@gmail.com"}]' \
    '[{"attr_key":"role","attr_value":"Trader"},{"attr_key":"company","attr_value":"Acme Capital"},{"attr_key":"desk","attr_value":"Proprietary Trading"}]'

create_entity "Sarah Chen" "person" \
    '[{"handle_type":"email","handle_value":"sarah.chen@aurora-partners.com","is_primary":true},{"handle_type":"bloomberg_id","handle_value":"schen@bloomberg.net"}]' \
    '[{"attr_key":"role","attr_value":"Analyst"},{"attr_key":"company","attr_value":"Aurora Partners"}]'

create_entity "David Park" "person" \
    '[{"handle_type":"email","handle_value":"david.park@acme-capital.com","is_primary":true},{"handle_type":"teams_id","handle_value":"david.park@teams.acme-capital.com"}]' \
    '[{"attr_key":"role","attr_value":"Managing Director"},{"attr_key":"company","attr_value":"Acme Capital"}]'

create_entity "Lisa Torres" "person" \
    '[{"handle_type":"email","handle_value":"lisa.torres@acme-capital.com","is_primary":true},{"handle_type":"teams_id","handle_value":"lisa.torres@teams.acme-capital.com"}]' \
    '[{"attr_key":"role","attr_value":"Chief Compliance Officer"},{"attr_key":"company","attr_value":"Acme Capital"}]'

create_entity "Rachel Kim" "person" \
    '[{"handle_type":"email","handle_value":"rachel.kim@acme-capital.com","is_primary":true},{"handle_type":"teams_id","handle_value":"rachel.kim@teams.acme-capital.com"}]' \
    '[{"attr_key":"role","attr_value":"Client Relationship Manager"},{"attr_key":"company","attr_value":"Acme Capital"}]'

info "Entity seeding complete"

# ─── Step 2: Seed alert rules via PostgreSQL ──────────────────────────────────
step "Step 2: Seed alert rules (risk model, policies, rules)"

kubectl exec -n umbrella-storage "$PG_POD" -- \
  psql -U postgres -d umbrella -c "
-- Risk Model: Market Abuse Detection
INSERT INTO policy.risk_models (id, name, description, is_active, created_by)
VALUES (
  '11111111-de00-0000-0000-000000000001',
  'Market Abuse Detection',
  'Detects potential market abuse including insider trading, front-running, and information leakage',
  true,
  '00000000-0000-0000-0000-000000000001'
) ON CONFLICT (id) DO NOTHING;

-- Policy 1: Insider Trading Indicators (HIGH)
INSERT INTO policy.policies (id, risk_model_id, name, description, is_active, created_by)
VALUES (
  '22222222-de00-0000-0000-000000000001',
  '11111111-de00-0000-0000-000000000001',
  'Insider Trading Indicators',
  'Flags communications containing insider trading signals',
  true,
  '00000000-0000-0000-0000-000000000001'
) ON CONFLICT (id) DO NOTHING;

-- Rule 1a: Confidential Meridian references
INSERT INTO policy.rules (id, policy_id, name, description, kql, severity, is_active, created_by)
VALUES (
  '33333333-de00-0000-0000-000000000001',
  '22222222-de00-0000-0000-000000000001',
  'Confidential Meridian References',
  'Flags messages mentioning Meridian/MRDN alongside confidential or acquisition language',
  'body_text:(confidential AND (meridian OR MRDN OR acquisition))',
  'high',
  true,
  '00000000-0000-0000-0000-000000000001'
) ON CONFLICT (id) DO NOTHING;

-- Rule 1b: Secrecy language
INSERT INTO policy.rules (id, policy_id, name, description, kql, severity, is_active, created_by)
VALUES (
  '33333333-de00-0000-0000-000000000002',
  '22222222-de00-0000-0000-000000000001',
  'Secrecy Language Detection',
  'Flags messages containing phrases that suggest information concealment',
  'body_text:(\"didn''t hear it from me\" OR \"don''t tell anyone\" OR \"keep between us\" OR \"no paper trail\")',
  'high',
  true,
  '00000000-0000-0000-0000-000000000001'
) ON CONFLICT (id) DO NOTHING;

-- Rule 1c: Coded trading language
INSERT INTO policy.rules (id, policy_id, name, description, kql, severity, is_active, created_by)
VALUES (
  '33333333-de00-0000-0000-000000000003',
  '22222222-de00-0000-0000-000000000001',
  'Coded Trading Language',
  'Flags messages using known coded language patterns for trading activity',
  'body_text:(repositioned AND (weather OR garden OR forecast))',
  'high',
  true,
  '00000000-0000-0000-0000-000000000001'
) ON CONFLICT (id) DO NOTHING;

-- Policy 2: Unusual Trading Patterns (MEDIUM)
INSERT INTO policy.policies (id, risk_model_id, name, description, is_active, created_by)
VALUES (
  '22222222-de00-0000-0000-000000000002',
  '11111111-de00-0000-0000-000000000001',
  'Unusual Trading Patterns',
  'Flags unusual trading volume and patterns',
  true,
  '00000000-0000-0000-0000-000000000001'
) ON CONFLICT (id) DO NOTHING;

-- Rule 2a: Large MRDN trades
INSERT INTO policy.rules (id, policy_id, name, description, kql, severity, is_active, created_by)
VALUES (
  '33333333-de00-0000-0000-000000000004',
  '22222222-de00-0000-0000-000000000002',
  'Large MRDN Trade',
  'Flags MRDN trades with quantity >= 5000',
  'body_text:(MRDN AND (5,000 OR 8,000 OR 10,000 OR 26,500))',
  'medium',
  true,
  '00000000-0000-0000-0000-000000000001'
) ON CONFLICT (id) DO NOTHING;

-- Policy 3: Off-Channel Communication (MEDIUM)
INSERT INTO policy.policies (id, risk_model_id, name, description, is_active, created_by)
VALUES (
  '22222222-de00-0000-0000-000000000003',
  '11111111-de00-0000-0000-000000000001',
  'Off-Channel Communication',
  'Detects attempts to move sensitive communications off monitored channels',
  true,
  '00000000-0000-0000-0000-000000000001'
) ON CONFLICT (id) DO NOTHING;

-- Rule 3a: Personal email forwarding of confidential content
INSERT INTO policy.rules (id, policy_id, name, description, kql, severity, is_active, created_by)
VALUES (
  '33333333-de00-0000-0000-000000000005',
  '22222222-de00-0000-0000-000000000003',
  'Off-Channel Forward Detection',
  'Flags forwarding of potentially sensitive content to personal email or external channels',
  'body_text:(\"saving for my records\" OR \"forwarded message\" OR \"personal email\") AND body_text:(confidential OR meridian)',
  'medium',
  true,
  '00000000-0000-0000-0000-000000000001'
) ON CONFLICT (id) DO NOTHING;

-- Decision statuses (idempotent)
INSERT INTO review.decision_statuses (id, name, description, is_terminal)
VALUES
  ('eeeeeeee-0000-0000-0000-000000000001', 'Escalate',     'Escalate for further review', false),
  ('eeeeeeee-0000-0000-0000-000000000002', 'No Breach',    'Reviewed — no policy breach', true),
  ('eeeeeeee-0000-0000-0000-000000000003', 'Breach Found', 'Confirmed policy breach',     true)
ON CONFLICT (id) DO NOTHING;
"

info "Alert rules seeded"

# ─── Step 3: Sync percolator rules ───────────────────────────────────────────
step "Step 3: Sync percolator rules to Elasticsearch"

# Ensure port-forward is still alive (Step 2's kubectl exec may have disrupted it)
if ! curl -s --max-time 2 http://localhost:8001/docs >/dev/null 2>&1; then
    info "Restarting UI backend port-forward..."
    for pid in "${PF_PIDS[@]}"; do kill "$pid" 2>/dev/null || true; done
    PF_PIDS=()
    start_port_forward umbrella-ui umbrella-ui-backend 8001 8000
    TOKEN=$(generate_token admin)
fi

SYNC_RESPONSE=$(curl -s --max-time 60 -w "\n%{http_code}" -X POST \
    -H "Authorization: Bearer $TOKEN" \
    "http://localhost:8001/api/v1/alert-generation/sync-rules") || true
SYNC_HTTP=$(echo "$SYNC_RESPONSE" | tail -1)
SYNC_BODY=$(echo "$SYNC_RESPONSE" | sed '$d')

if [ "$SYNC_HTTP" = "200" ]; then
    UPSERTED=$(echo "$SYNC_BODY" | jq -r '.upserted // 0' 2>/dev/null)
    info "Percolator rules synced: $UPSERTED rule(s)"
else
    warn "Percolator sync returned HTTP $SYNC_HTTP: $SYNC_BODY"
fi

# ─── Step 4: Send emails via SMTP ────────────────────────────────────────────
step "Step 4: Send emails via SMTP (through real pipeline)"

# Generate demo data
info "Generating demo data..."
DEMO_DATA=$(uv run --project connectors/connector-framework python scripts/demo-data/generate_demo_data.py)

# Extract emails and send via SMTP
EMAIL_COUNT=$(echo "$DEMO_DATA" | jq '.emails | length')
info "Sending $EMAIL_COUNT emails via SMTP..."

# Pipe email JSON via stdin to avoid control-character escaping issues
kubectl delete pod demo-smtp-sender -n umbrella-connectors --ignore-not-found 2>/dev/null || true
echo "$DEMO_DATA" | jq -c '.emails' | \
kubectl run demo-smtp-sender --rm -i --image=umbrella-email:latest --image-pull-policy=Never \
  -n umbrella-connectors --restart=Never -- \
  python3 -c "
import json, sys, smtplib
from email.message import EmailMessage

emails = json.load(sys.stdin)

with smtplib.SMTP('mailserver.umbrella-connectors.svc', 25) as server:
    for i, e in enumerate(emails):
        msg = EmailMessage()
        msg['From'] = e['from']
        msg['To'] = ', '.join(e['to'])
        msg['Subject'] = e['subject']
        msg['Message-ID'] = e['message_id']
        msg['Date'] = e['date']
        if e.get('cc'):
            msg['Cc'] = e['cc']
        msg.set_content(e['body'])
        server.send_message(msg)
        print(f'  [{i+1}/{len(emails)}] Sent: {e[\"subject\"][:60]}')

print(f'Done — {len(emails)} emails sent')
"

info "All emails sent"

# ─── Step 5: Publish chats + trades + calls to Kafka ─────────────────────────
step "Step 5: Publish normalized messages to Kafka (chats, trades, calls)"

NORMALIZED_COUNT=$(echo "$DEMO_DATA" | jq '.normalized_messages | length')
info "Publishing $NORMALIZED_COUNT normalized messages to Kafka..."

# Non-trade messages → normalized-messages
NON_TRADE_LINES=$(echo "$DEMO_DATA" | jq -c '.normalized_messages[] | select(.channel != "trade_data")')

kubectl delete pod demo-kafka-producer -n umbrella-streaming --ignore-not-found 2>/dev/null || true
echo "$NON_TRADE_LINES" | kubectl run demo-kafka-producer --rm -i \
  --image=apache/kafka:4.1.1 -n umbrella-streaming --restart=Never -- \
  /opt/kafka/bin/kafka-console-producer.sh \
  --bootstrap-server kafka:9092 \
  --topic normalized-messages

# Trade messages → normalized-trades
TRADE_LINES=$(echo "$DEMO_DATA" | jq -c '.normalized_messages[] | select(.channel == "trade_data")')
kubectl delete pod demo-kafka-producer -n umbrella-streaming --ignore-not-found 2>/dev/null || true
echo "$TRADE_LINES" | kubectl run demo-kafka-producer --rm -i \
  --image=apache/kafka:4.1.1 -n umbrella-streaming --restart=Never -- \
  /opt/kafka/bin/kafka-console-producer.sh \
  --bootstrap-server kafka:9092 \
  --topic normalized-trades

CHAT_COUNT=$(echo "$DEMO_DATA" | jq '[.normalized_messages[] | select(.channel == "teams_chat")] | length')
TRADE_COUNT=$(echo "$DEMO_DATA" | jq '[.normalized_messages[] | select(.channel == "trade_data")] | length')
CALL_COUNT=$(echo "$DEMO_DATA" | jq '[.normalized_messages[] | select(.channel == "teams_calls")] | length')
info "Published: $CHAT_COUNT chats, $TRADE_COUNT trades, $CALL_COUNT calls"

# ─── Step 6: Wait for pipeline processing ────────────────────────────────────
step "Step 6: Wait for pipeline processing"

info "Waiting 60 seconds for emails to flow through the pipeline..."
for i in {60..1}; do
    echo -ne "\rWaiting... ${i}s "
    sleep 1
done
echo ""

# ─── Step 7: Verify & report ─────────────────────────────────────────────────
step "Step 7: Verify and report"

# Port-forward Elasticsearch
start_port_forward umbrella-storage elasticsearch 9200 9200

# Count documents by channel in ES
info "Checking Elasticsearch document counts..."

es_count_channel() {
    local channel="$1"
    curl -s "http://localhost:9200/messages-*/_count" \
        -H "Content-Type: application/json" \
        -d "{\"query\":{\"term\":{\"channel\":\"$channel\"}}}" 2>/dev/null | jq -r '.count // 0'
}

ES_EMAIL_COUNT=$(es_count_channel "email")
ES_CHAT_COUNT=$(es_count_channel "teams_chat")
ES_TRADE_COUNT=$(curl -s "http://localhost:9200/trades-*/_count" \
    -H "Content-Type: application/json" \
    -d '{"query":{"match_all":{}}}' 2>/dev/null | jq -r '.count // 0')
ES_CALL_COUNT=$(es_count_channel "teams_calls")
ES_TOTAL=$((ES_EMAIL_COUNT + ES_CHAT_COUNT + ES_TRADE_COUNT + ES_CALL_COUNT))

info "Elasticsearch documents:"
echo "  Email:      $ES_EMAIL_COUNT"
echo "  Teams Chat: $ES_CHAT_COUNT"
echo "  Trade Data: $ES_TRADE_COUNT"
echo "  Calls:      $ES_CALL_COUNT"
echo "  Total:      $ES_TOTAL"

# Run batch alert generation
info "Running batch alert generation..."
JOB_RESPONSE=$(curl -s -X POST \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    "http://localhost:8001/api/v1/alert-generation/jobs" \
    -d '{"scope_type":"all","query_kql":"*"}')
JOB_ID=$(echo "$JOB_RESPONSE" | jq -r '.id // empty' 2>/dev/null)

ALERTS_CREATED=0
if [ -n "$JOB_ID" ] && [ "$JOB_ID" != "null" ]; then
    info "Alert generation job created: id=$JOB_ID"

    # Poll until complete
    for attempt in $(seq 1 24); do
        sleep 5
        POLL=$(curl -s -H "Authorization: Bearer $TOKEN" \
            "http://localhost:8001/api/v1/alert-generation/jobs/$JOB_ID")
        JOB_STATUS=$(echo "$POLL" | jq -r '.status // empty')
        ALERTS_CREATED=$(echo "$POLL" | jq -r '.alerts_created // 0')
        RULES_EVALUATED=$(echo "$POLL" | jq -r '.rules_evaluated // 0')
        DOCS_SCANNED=$(echo "$POLL" | jq -r '.documents_scanned // 0')

        if [ "$JOB_STATUS" = "completed" ] || [ "$JOB_STATUS" = "failed" ]; then
            break
        fi
        echo -ne "\r  Job status: $JOB_STATUS (attempt $attempt/24)..."
    done
    echo ""

    if [ "$JOB_STATUS" = "completed" ]; then
        info "Alert generation completed: rules=$RULES_EVALUATED docs=$DOCS_SCANNED alerts=$ALERTS_CREATED"
    else
        warn "Alert generation ended with status=$JOB_STATUS"
        ERROR_MSG=$(echo "$POLL" | jq -r '.error_message // empty')
        [ -n "$ERROR_MSG" ] && warn "  Error: $ERROR_MSG"
    fi
else
    warn "Failed to create alert generation job (response: $JOB_RESPONSE)"
fi

# Check alert count from PostgreSQL
PG_ALERT_COUNT=$(kubectl exec -n umbrella-storage "$PG_POD" -- \
  psql -U postgres -d umbrella -tAc \
  "SELECT COUNT(*) FROM alert.alerts WHERE rule_id IN (
    '33333333-de00-0000-0000-000000000001',
    '33333333-de00-0000-0000-000000000002',
    '33333333-de00-0000-0000-000000000003',
    '33333333-de00-0000-0000-000000000004',
    '33333333-de00-0000-0000-000000000005'
  );" 2>/dev/null || echo "0")
PG_ALERT_COUNT="${PG_ALERT_COUNT//[[:space:]]/}"

# Cross-channel entity summary for Marcus Webb
MARCUS_MSG_COUNT=0
MARCUS_ENTITY_ID="${ENTITY_IDS[Marcus Webb]:-}"
if [ -n "$MARCUS_ENTITY_ID" ]; then
    MARCUS_RESP=$(curl -s -H "Authorization: Bearer $TOKEN" \
        "http://localhost:8001/api/v1/entities/$MARCUS_ENTITY_ID/messages?offset=0&limit=1")
    MARCUS_MSG_COUNT=$(echo "$MARCUS_RESP" | jq -r '.total // 0' 2>/dev/null || echo "0")
fi

# ─── Summary ──────────────────────────────────────────────────────────────────
echo ""
echo "=========================================="
echo "Demo Results Summary"
echo "=========================================="
echo ""
echo "Elasticsearch Documents:"
echo "  Email:         $([ "$ES_EMAIL_COUNT" -gt 0 ]  && printf "${GREEN}$ES_EMAIL_COUNT${NC}" || printf "${RED}$ES_EMAIL_COUNT${NC}")"
echo "  Teams Chat:    $([ "$ES_CHAT_COUNT" -gt 0 ]   && printf "${GREEN}$ES_CHAT_COUNT${NC}" || printf "${RED}$ES_CHAT_COUNT${NC}")"
echo "  Trade Data:    $([ "$ES_TRADE_COUNT" -gt 0 ]  && printf "${GREEN}$ES_TRADE_COUNT${NC}" || printf "${RED}$ES_TRADE_COUNT${NC}")"
echo "  Calls:         $([ "$ES_CALL_COUNT" -gt 0 ]   && printf "${GREEN}$ES_CALL_COUNT${NC}" || printf "${RED}$ES_CALL_COUNT${NC}")"
echo ""
echo "Alerts Generated: $([ "$PG_ALERT_COUNT" -gt 0 ] && printf "${GREEN}$PG_ALERT_COUNT${NC}" || printf "${YELLOW}$PG_ALERT_COUNT${NC}")"
echo ""
echo "Marcus Webb Cross-Channel Messages: $([ "$MARCUS_MSG_COUNT" -gt 0 ] && printf "${GREEN}$MARCUS_MSG_COUNT${NC}" || printf "${YELLOW}$MARCUS_MSG_COUNT${NC}")"
echo ""

# Pass/fail checks
PASS=0
FAIL=0

check() {
    local name="$1" value="$2"
    if [ "$value" -gt 0 ]; then
        printf "  ${GREEN}[PASS]${NC} %s\n" "$name"
        PASS=$((PASS + 1))
    else
        printf "  ${RED}[FAIL]${NC} %s\n" "$name"
        FAIL=$((FAIL + 1))
    fi
}

echo "Checks:"
check "Emails indexed in ES"          "$ES_EMAIL_COUNT"
check "Chats indexed in ES"           "$ES_CHAT_COUNT"
check "Trades indexed in ES"          "$ES_TRADE_COUNT"
check "Calls indexed in ES"           "$ES_CALL_COUNT"
check "Alerts generated"              "$PG_ALERT_COUNT"
check "Marcus Webb entity messages"   "$MARCUS_MSG_COUNT"

echo ""
echo "=========================================="
if [ "$FAIL" -eq 0 ]; then
    info "DEMO COMPLETE — All $PASS checks passed!"
else
    warn "DEMO COMPLETE — $PASS passed, $FAIL failed"
fi
echo "=========================================="
echo ""

info "To explore the demo data:"
echo "  UI:      kubectl port-forward -n umbrella-ui svc/umbrella-ui-frontend 3000:80"
echo "           Open http://localhost:3000 — login with testadmin / testpass123"
echo ""
echo "  Search for 'Marcus Webb' to see cross-channel activity"
echo "  Search for 'Meridian' to see suspicious communications"
echo "  Check Alerts page to review generated alerts"
echo ""
echo "  Kibana:  kubectl port-forward -n umbrella-storage svc/kibana 5601:5601"
echo "           Open http://localhost:5601 (index pattern: messages-*)"
echo ""
echo "  ES API:  kubectl port-forward -n umbrella-storage svc/elasticsearch 9200:9200"
echo "           curl localhost:9200/messages-*/_search?q=channel:trade_data"

if [ "$FAIL" -gt 0 ]; then
    echo ""
    error "Debugging:"
    echo "  kubectl logs -n umbrella-connectors -l app=email-connector --tail=30"
    echo "  kubectl logs -n umbrella-connectors -l app=email-processor --tail=30"
    echo "  kubectl logs -n umbrella-ingestion -l app=ingestion-service --tail=30"
    echo "  kubectl logs -n umbrella-storage -l app=logstash --tail=30"
    echo "  kubectl logs -n umbrella-ui -l app=umbrella-ui-backend --tail=30"
    exit 1
fi
