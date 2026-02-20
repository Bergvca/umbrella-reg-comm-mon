#!/usr/bin/env bash
# Seed compliance risk models, policies, and rules into Umbrella.
#
# Creates 3 risk models, 5 policies, and 25 rules covering:
#   - Market Abuse       (Insider Trading Detection, Market Manipulation)
#   - Conduct & Compliance (Off-Channel Communications, Client Mis-selling)
#   - Anti-Money Laundering (Suspicious Transaction Patterns)
#
# Safe to re-run — all INSERTs use ON CONFLICT (id) DO NOTHING.
# Requires: scripts/deploy-minikube.sh and scripts/test-pipeline-minikube.sh
# to have been run first (cluster up, testadmin user seeded).
#
# Re-exec under bash if invoked with sh/dash
[ -z "$BASH_VERSION" ] && exec bash "$0" "$@"

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

echo "=========================================="
echo "Umbrella Policy Seed"
echo "=========================================="
echo ""

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { printf "${GREEN}[INFO]${NC} %s\n" "$1"; }
warn()  { printf "${YELLOW}[WARN]${NC} %s\n" "$1"; }
error() { printf "${RED}[ERROR]${NC} %s\n" "$1"; }

# ---------------------------------------------------------------------------
# 1. Guard: cluster must be up
# ---------------------------------------------------------------------------
if ! kubectl get ns umbrella-storage &>/dev/null; then
    error "umbrella-storage namespace not found."
    error "Run scripts/deploy-minikube.sh first, then scripts/test-pipeline-minikube.sh."
    exit 1
fi

PG_POD=$(kubectl get pod -n umbrella-storage -l app=postgresql \
    -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
if [ -z "$PG_POD" ]; then
    error "No PostgreSQL pod found in umbrella-storage namespace."
    exit 1
fi
info "PostgreSQL pod: $PG_POD"

# ---------------------------------------------------------------------------
# 2. Resolve seed user (testadmin preferred, fallback to known test UUID)
# ---------------------------------------------------------------------------
SEED_USER=$(kubectl exec -n umbrella-storage "$PG_POD" -- \
    psql -U postgres -d umbrella -tAc \
    "SELECT id FROM iam.users WHERE username = 'testadmin' LIMIT 1;" \
    2>/dev/null || true)

if [ -z "$SEED_USER" ]; then
    SEED_USER='00000000-0000-0000-0000-000000000001'
    warn "testadmin not found; using fallback UUID $SEED_USER"
else
    info "Seed user: testadmin ($SEED_USER)"
fi

# ---------------------------------------------------------------------------
# 3. Insert everything
#    UUIDs are fixed so the script is idempotent across runs.
#    Risk models:  11111111-0000-0000-0000-00000000000{1-3}
#    Policies:     22222222-0000-0000-0000-00000000000{1-5}
#    Rules:        33333333-0000-0000-0000-0000000000{01-25}
# ---------------------------------------------------------------------------
info "Seeding risk models, policies, and rules..."

kubectl exec -n umbrella-storage "$PG_POD" -i -- \
    psql -U postgres -d umbrella -v ON_ERROR_STOP=1 << SQL

-- ============================================================
-- Risk Models
-- ============================================================
INSERT INTO policy.risk_models (id, name, description, is_active, created_by) VALUES
  (
    '11111111-0000-0000-0000-000000000001',
    'Market Abuse',
    'Detects insider trading and market manipulation in communications (SEC 17a-4, CFTC 1.31, FED SR 13-19)',
    true,
    '$SEED_USER'
  ),
  (
    '11111111-0000-0000-0000-000000000002',
    'Conduct & Compliance',
    'Supervises off-channel communications, client mis-selling, and FINRA 3110 obligations',
    true,
    '$SEED_USER'
  ),
  (
    '11111111-0000-0000-0000-000000000003',
    'Anti-Money Laundering',
    'Flags AML red flags: structuring, layering, sanctions evasion, and cash conversion (CFTC 1.31, BSA)',
    true,
    '$SEED_USER'
  )
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- Policies
-- ============================================================
INSERT INTO policy.policies (id, risk_model_id, name, description, is_active, created_by) VALUES
  (
    '22222222-0000-0000-0000-000000000001',
    '11111111-0000-0000-0000-000000000001',
    'Insider Trading Detection',
    'Identifies communications indicating misuse of material non-public information',
    true,
    '$SEED_USER'
  ),
  (
    '22222222-0000-0000-0000-000000000002',
    '11111111-0000-0000-0000-000000000001',
    'Market Manipulation',
    'Detects coordinated trading, wash trades, spoofing, and price manipulation language',
    true,
    '$SEED_USER'
  ),
  (
    '22222222-0000-0000-0000-000000000003',
    '11111111-0000-0000-0000-000000000002',
    'Off-Channel Communications',
    'Flags use of personal apps, personal devices, and explicit attempts to avoid firm supervision',
    true,
    '$SEED_USER'
  ),
  (
    '22222222-0000-0000-0000-000000000004',
    '11111111-0000-0000-0000-000000000002',
    'Client Mis-selling',
    'Catches misleading sales language, return guarantees, pressure tactics, and discouragement of due diligence',
    true,
    '$SEED_USER'
  ),
  (
    '22222222-0000-0000-0000-000000000005',
    '11111111-0000-0000-0000-000000000003',
    'Suspicious Transaction Patterns',
    'Surfaces structuring, layering, shell entity references, and sanctions evasion indicators',
    true,
    '$SEED_USER'
  )
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- Rules: Insider Trading Detection (policy 1)
-- ============================================================
INSERT INTO policy.rules (id, policy_id, name, description, kql, severity, is_active, created_by) VALUES
  (
    '33333333-0000-0000-0000-000000000001',
    '22222222-0000-0000-0000-000000000001',
    'Non-Public Information Sharing',
    'Phrases indicating disclosure of material non-public information',
    'body_text: "you didn''t hear this from me" OR body_text: "before the announcement" OR body_text: "don''t tell anyone" OR body_text: "inside info"',
    'critical', true, '$SEED_USER'
  ),
  (
    '33333333-0000-0000-0000-000000000002',
    '22222222-0000-0000-0000-000000000001',
    'Pre-Announcement Trading Hint',
    'Hints to trade ahead of a corporate announcement or earnings release',
    'body_text: "front-run" OR body_text: "before results" OR body_text: "before it goes public" OR body_text: "tip"',
    'critical', true, '$SEED_USER'
  ),
  (
    '33333333-0000-0000-0000-000000000003',
    '22222222-0000-0000-0000-000000000001',
    'Embargoed Information Reference',
    'References to embargoed, restricted, or NDA-covered information',
    'body_text: "not for distribution" OR body_text: "under embargo" OR body_text: "under NDA" OR body_text: "confidential do not forward"',
    'critical', true, '$SEED_USER'
  ),
  (
    '33333333-0000-0000-0000-000000000004',
    '22222222-0000-0000-0000-000000000001',
    'Urgency Around Non-Public Event',
    'Unusual time pressure linked to an undisclosed corporate event',
    'body_text: "act fast" OR body_text: "before close" OR body_text: "move quickly" OR body_text: "time sensitive"',
    'high', true, '$SEED_USER'
  ),
  (
    '33333333-0000-0000-0000-000000000005',
    '22222222-0000-0000-0000-000000000001',
    'Information Barrier Breach',
    'Explicit attempt to cross or circumvent an information barrier',
    'body_text: "don''t tell compliance" OR body_text: "keep this between us" OR body_text: "around the chinese wall" OR body_text: "bypass the wall"',
    'critical', true, '$SEED_USER'
  )
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- Rules: Market Manipulation (policy 2)
-- ============================================================
INSERT INTO policy.rules (id, policy_id, name, description, kql, severity, is_active, created_by) VALUES
  (
    '33333333-0000-0000-0000-000000000006',
    '22222222-0000-0000-0000-000000000002',
    'Pump and Dump Language',
    'Promotes buying to artificially inflate a price before selling',
    'body_text: "pump" OR body_text: "push the price" OR body_text: "buy before" OR body_text: "moon"',
    'high', true, '$SEED_USER'
  ),
  (
    '33333333-0000-0000-0000-000000000007',
    '22222222-0000-0000-0000-000000000002',
    'Spoofing and Layering',
    'References to placing orders intended to be cancelled to mislead the market',
    'body_text: "spoof" OR body_text: "cancel the order" OR body_text: "layer the book"',
    'high', true, '$SEED_USER'
  ),
  (
    '33333333-0000-0000-0000-000000000008',
    '22222222-0000-0000-0000-000000000002',
    'Coordinated Trading',
    'Signals of coordinated buy or sell activity across multiple parties',
    'body_text: "all buy at once" OR body_text: "we all move together" OR body_text: "coordinate the trade" OR body_text: "synchronized"',
    'critical', true, '$SEED_USER'
  ),
  (
    '33333333-0000-0000-0000-000000000009',
    '22222222-0000-0000-0000-000000000002',
    'Wash Trading',
    'References to circular or self-dealing trades to create artificial volume',
    'body_text: "wash trade" OR body_text: "circular trade" OR body_text: "round trip" OR body_text: "buy from yourself"',
    'critical', true, '$SEED_USER'
  ),
  (
    '33333333-0000-0000-0000-000000000010',
    '22222222-0000-0000-0000-000000000002',
    'Marking the Close',
    'Attempts to influence the closing price of a security',
    'body_text: "mark the close" OR body_text: "end of day push" OR body_text: "push at close" OR body_text: "closing price target"',
    'high', true, '$SEED_USER'
  )
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- Rules: Off-Channel Communications (policy 3)
-- ============================================================
INSERT INTO policy.rules (id, policy_id, name, description, kql, severity, is_active, created_by) VALUES
  (
    '33333333-0000-0000-0000-000000000011',
    '22222222-0000-0000-0000-000000000003',
    'Personal App References',
    'Use of unsupervised consumer messaging platforms for business communications',
    'body_text: "whatsapp" OR body_text: "signal" OR body_text: "telegram" OR body_text: "text me instead" OR body_text: "personal email"',
    'high', true, '$SEED_USER'
  ),
  (
    '33333333-0000-0000-0000-000000000012',
    '22222222-0000-0000-0000-000000000003',
    'Evidence Destruction Hints',
    'Instructions to delete or avoid recording business communications',
    'body_text: "delete this" OR body_text: "don''t write that down" OR body_text: "don''t put in email" OR body_text: "off the record"',
    'critical', true, '$SEED_USER'
  ),
  (
    '33333333-0000-0000-0000-000000000013',
    '22222222-0000-0000-0000-000000000003',
    'Ephemeral and Encrypted App References',
    'Reference to apps with disappearing or end-to-end encrypted messages that evade capture',
    'body_text: "snapchat" OR body_text: "wickr" OR body_text: "threema" OR body_text: "disappearing messages"',
    'high', true, '$SEED_USER'
  ),
  (
    '33333333-0000-0000-0000-000000000014',
    '22222222-0000-0000-0000-000000000003',
    'Personal Device Instruction',
    'Directing a contact to reach out via a personal or unmonitored device',
    'body_text: "call my personal" OR body_text: "use my mobile" OR body_text: "private number" OR body_text: "my personal phone"',
    'medium', true, '$SEED_USER'
  ),
  (
    '33333333-0000-0000-0000-000000000015',
    '22222222-0000-0000-0000-000000000003',
    'Explicit Monitoring Avoidance',
    'Explicitly attempting to conduct business outside firm surveillance systems',
    'body_text: "not monitored" OR body_text: "not recorded" OR body_text: "outside the system" OR body_text: "away from the system"',
    'critical', true, '$SEED_USER'
  )
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- Rules: Client Mis-selling (policy 4)
-- ============================================================
INSERT INTO policy.rules (id, policy_id, name, description, kql, severity, is_active, created_by) VALUES
  (
    '33333333-0000-0000-0000-000000000016',
    '22222222-0000-0000-0000-000000000004',
    'Return Guarantees',
    'Promises of guaranteed investment returns, which are prohibited',
    'body_text: "guaranteed return" OR body_text: "can''t lose" OR body_text: "risk-free" OR body_text: "sure thing"',
    'high', true, '$SEED_USER'
  ),
  (
    '33333333-0000-0000-0000-000000000017',
    '22222222-0000-0000-0000-000000000004',
    'Risk Minimisation',
    'Misleadingly describes an investment product as having no material downside',
    'body_text: "nothing can go wrong" OR body_text: "completely safe" OR body_text: "no downside"',
    'medium', true, '$SEED_USER'
  ),
  (
    '33333333-0000-0000-0000-000000000018',
    '22222222-0000-0000-0000-000000000004',
    'High-Pressure Sales Tactics',
    'Creates artificial urgency to pressure a client into a decision',
    'body_text: "limited time offer" OR body_text: "act now" OR body_text: "won''t last" OR body_text: "last chance to invest"',
    'medium', true, '$SEED_USER'
  ),
  (
    '33333333-0000-0000-0000-000000000019',
    '22222222-0000-0000-0000-000000000004',
    'Discouraging Due Diligence',
    'Dissuades a client from reading or reviewing product documentation',
    'body_text: "just sign here" OR body_text: "don''t worry about the details" OR body_text: "you don''t need to read" OR body_text: "trust me on this"',
    'high', true, '$SEED_USER'
  ),
  (
    '33333333-0000-0000-0000-000000000020',
    '22222222-0000-0000-0000-000000000004',
    'Misleading Performance Claims',
    'Cites unverifiable or demonstrably false historical performance figures',
    'body_text: "always goes up" OR body_text: "never had a loss" OR body_text: "100% track record" OR body_text: "beats the market every year"',
    'high', true, '$SEED_USER'
  )
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- Rules: Suspicious Transaction Patterns (policy 5)
-- ============================================================
INSERT INTO policy.rules (id, policy_id, name, description, kql, severity, is_active, created_by) VALUES
  (
    '33333333-0000-0000-0000-000000000021',
    '22222222-0000-0000-0000-000000000005',
    'Structuring Hints',
    'Suggests breaking up transactions to stay below regulatory reporting thresholds',
    'body_text: "keep it under" OR body_text: "split the payment" OR body_text: "stay below the limit" OR body_text: "cash only"',
    'critical', true, '$SEED_USER'
  ),
  (
    '33333333-0000-0000-0000-000000000022',
    '22222222-0000-0000-0000-000000000005',
    'Layering Language',
    'Describes moving funds through multiple accounts to obscure origin or ownership',
    'body_text: "move the funds through" OR body_text: "transfer then re-transfer" OR body_text: "pass it through"',
    'high', true, '$SEED_USER'
  ),
  (
    '33333333-0000-0000-0000-000000000023',
    '22222222-0000-0000-0000-000000000005',
    'Shell and Nominee Entity References',
    'References to entities commonly used to disguise beneficial ownership',
    'body_text: "shell company" OR body_text: "nominee account" OR body_text: "front company" OR body_text: "beneficial owner"',
    'critical', true, '$SEED_USER'
  ),
  (
    '33333333-0000-0000-0000-000000000024',
    '22222222-0000-0000-0000-000000000005',
    'Sanctions Evasion Language',
    'Explicit intent to circumvent sanctions regimes or regulatory controls',
    'body_text: "avoid sanctions" OR body_text: "bypass controls" OR body_text: "get around restrictions" OR body_text: "evade"',
    'critical', true, '$SEED_USER'
  ),
  (
    '33333333-0000-0000-0000-000000000025',
    '22222222-0000-0000-0000-000000000005',
    'Cash Conversion and No Trace',
    'Discusses untraceable, cash-only, or off-ledger transactions',
    'body_text: "no paper trail" OR body_text: "untraceable" OR body_text: "convert to cash" OR body_text: "clean the money"',
    'critical', true, '$SEED_USER'
  )
ON CONFLICT (id) DO NOTHING;

SQL

# ---------------------------------------------------------------------------
# 4. Summary
# ---------------------------------------------------------------------------
info "Seed complete. Summary:"
echo ""

kubectl exec -n umbrella-storage "$PG_POD" -- \
    psql -U postgres -d umbrella \
    -c "
SELECT
    rm.name        AS \"Risk Model\",
    p.name         AS \"Policy\",
    COUNT(r.id)    AS \"Rules\"
FROM policy.risk_models rm
JOIN policy.policies p ON p.risk_model_id = rm.id
JOIN policy.rules    r ON r.policy_id     = p.id
WHERE rm.id IN (
    '11111111-0000-0000-0000-000000000001',
    '11111111-0000-0000-0000-000000000002',
    '11111111-0000-0000-0000-000000000003'
)
GROUP BY rm.name, p.name
ORDER BY rm.name, p.name;
"

echo ""
kubectl exec -n umbrella-storage "$PG_POD" -- \
    psql -U postgres -d umbrella \
    -c "
SELECT
    COUNT(DISTINCT rm.id) AS \"Risk Models\",
    COUNT(DISTINCT p.id)  AS \"Policies\",
    COUNT(r.id)           AS \"Rules\"
FROM policy.risk_models rm
JOIN policy.policies p ON p.risk_model_id = rm.id
JOIN policy.rules    r ON r.policy_id     = p.id
WHERE rm.id IN (
    '11111111-0000-0000-0000-000000000001',
    '11111111-0000-0000-0000-000000000002',
    '11111111-0000-0000-0000-000000000003'
);
"

echo ""
echo "=========================================="
info "Done."
echo "=========================================="
