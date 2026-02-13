#!/usr/bin/env bash
# End-to-end pipeline test in minikube
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

# 3. Build Python service images
info "Building Docker images..."
./scripts/build-images.sh

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

info "Deploying MinIO..."
kubectl apply -f deploy/k8s/umbrella-storage/minio/
kubectl rollout status deployment/minio -n umbrella-storage --timeout=120s

info "Deploying Elasticsearch..."
kubectl apply -f deploy/k8s/umbrella-storage/elasticsearch/
kubectl rollout status statefulset/elasticsearch -n umbrella-storage --timeout=300s

info "Deploying Logstash..."
kubectl apply -f deploy/k8s/umbrella-storage/logstash/
kubectl rollout status deployment/logstash -n umbrella-storage --timeout=300s

# 5. Deploy Python services
info "Deploying email-processor..."
kubectl apply -f deploy/k8s/umbrella-connectors/namespace.yaml
kubectl apply -f deploy/k8s/umbrella-connectors/
kubectl wait --for=condition=ready pod -l app=email-processor -n umbrella-connectors --timeout=300s

info "Deploying ingestion-service..."
kubectl apply -f deploy/k8s/umbrella-ingestion/namespace.yaml
kubectl apply -f deploy/k8s/umbrella-ingestion/
kubectl wait --for=condition=ready pod -l app=ingestion-service -n umbrella-ingestion --timeout=120s

info "All services deployed successfully!"
echo ""

# 6. Wait a bit for services to stabilize
info "Waiting 10 seconds for services to stabilize..."
sleep 10

# 7. Upload test EML to MinIO
info "Uploading test EML file to MinIO..."

# Create test EML content
TEST_EML_PATH="/tmp/test-email-001.eml"
cat > "$TEST_EML_PATH" << 'EOF'
From: alice@example.com
To: bob@acme.com
Subject: Test Email - Pipeline Validation
Date: Wed, 12 Feb 2026 10:00:00 +0000
Message-ID: <test-001@example.com>
Content-Type: text/plain; charset=utf-8

This is a test email message for validating the Umbrella pipeline.

The message should flow through:
1. Email Processor (parse EML)
2. Ingestion Service (normalize)
3. Logstash (index)
4. Elasticsearch (store)

If you can search for this in Elasticsearch, the pipeline is working!

--
Test Message
EOF

# Upload to MinIO using kubectl run with mc client
info "Creating MinIO bucket and uploading test EML..."
kubectl delete pod mc-upload -n umbrella-storage --ignore-not-found
kubectl run mc-upload --rm -i --image=minio/mc -n umbrella-storage \
  --command -- /bin/sh -c \
  "mc alias set local http://minio:9000 minioadmin minioadmin && \
   mc mb --ignore-existing local/umbrella/raw/email && \
   cat | mc pipe local/umbrella/raw/email/test-001.eml" < "$TEST_EML_PATH"

info "Test EML uploaded to s3://umbrella/raw/email/test-001.eml"

# 8. Inject test RawMessage to raw-messages topic
info "Injecting RawMessage to Kafka raw-messages topic..."
kubectl delete pod kafka-producer -n umbrella-streaming --ignore-not-found

# Create RawMessage JSON
TEST_MESSAGE=$(cat <<EOF
{
  "raw_message_id": "test-001",
  "channel": "email",
  "raw_payload": {
    "envelope": {
      "message_id": "<test-001@example.com>",
      "subject": "Test Email - Pipeline Validation",
      "from": "alice@example.com",
      "to": ["bob@acme.com"],
      "cc": [],
      "bcc": [],
      "date": "Wed, 12 Feb 2026 10:00:00 +0000"
    },
    "s3_uri": "s3://umbrella/raw/email/test-001.eml",
    "size_bytes": 500
  },
  "raw_format": "eml_ref",
  "metadata": {
    "imap_uid": "1",
    "mailbox": "INBOX",
    "imap_host": "test"
  },
  "ingested_at": "2026-02-12T10:00:00Z"
}
EOF
)

# Compact to single line so kafka-console-producer sends it as one message
TEST_MESSAGE_COMPACT=$(echo "$TEST_MESSAGE" | python3 -c "import json,sys; print(json.dumps(json.load(sys.stdin)))")

kubectl run kafka-producer --rm -i --image=apache/kafka:4.1.1 -n umbrella-streaming -- \
  sh -c "/opt/kafka/bin/kafka-console-producer.sh --bootstrap-server kafka:9092 --topic raw-messages" <<< "$TEST_MESSAGE_COMPACT"

info "RawMessage injected to raw-messages topic"
echo ""

# 9. Wait for pipeline to process (give it 30 seconds)
info "Waiting 30 seconds for pipeline to process the message..."
for i in {30..1}; do
    echo -ne "\rWaiting... ${i}s "
    sleep 1
done
echo ""
echo ""

# 10. Verify: check each stage
info "Verifying message flow through pipeline..."
echo ""

# Check parsed-messages topic
info "Checking parsed-messages topic..."
kubectl delete pod kafka-check-parsed kafka-check-normalized -n umbrella-streaming --ignore-not-found 2>/dev/null || true
PARSED_COUNT=$(kubectl run kafka-check-parsed --rm -i --image=apache/kafka:4.1.1 -n umbrella-streaming -- \
  /opt/kafka/bin/kafka-get-offsets.sh \
  --bootstrap-server kafka:9092 \
  --topic parsed-messages 2>/dev/null | awk -F':' '{sum += $3} END {print sum+0}')

if [ "$PARSED_COUNT" -gt 0 ]; then
    info "✓ Found $PARSED_COUNT message(s) in parsed-messages topic"
else
    warn "✗ No messages found in parsed-messages topic"
fi

# Check normalized-messages topic
info "Checking normalized-messages topic..."
NORMALIZED_COUNT=$(kubectl run kafka-check-normalized --rm -i --image=apache/kafka:4.1.1 -n umbrella-streaming -- \
  /opt/kafka/bin/kafka-get-offsets.sh \
  --bootstrap-server kafka:9092 \
  --topic normalized-messages 2>/dev/null | awk -F':' '{sum += $3} END {print sum+0}')

if [ "$NORMALIZED_COUNT" -gt 0 ]; then
    info "✓ Found $NORMALIZED_COUNT message(s) in normalized-messages topic"
else
    warn "✗ No messages found in normalized-messages topic"
fi

# Check Elasticsearch
info "Checking Elasticsearch..."
info "Port-forwarding Elasticsearch..."
kubectl port-forward -n umbrella-storage svc/elasticsearch 9200:9200 >/dev/null 2>&1 &
PF_PID=$!
sleep 5

# Query Elasticsearch
ES_RESULT=$(curl -s http://localhost:9200/messages-*/_search?q=test-001 | jq -r '.hits.total.value // 0' 2>/dev/null || echo "0")

kill $PF_PID 2>/dev/null || true

if [ "$ES_RESULT" -gt 0 ]; then
    info "✓ Found $ES_RESULT document(s) in Elasticsearch"
else
    warn "✗ No documents found in Elasticsearch"
fi

echo ""
echo "=========================================="
echo "Pipeline Test Summary"
echo "=========================================="
echo "Stage 1 (IMAP Connector):    [SKIPPED - no IMAP server]"
echo "Stage 2 (Email Processor):   $([ "$PARSED_COUNT" -gt 0 ] && echo '[✓ PASS]' || echo '[✗ FAIL]')"
echo "Stage 3 (Ingestion Service): $([ "$NORMALIZED_COUNT" -gt 0 ] && echo '[✓ PASS]' || echo '[✗ FAIL]')"
echo "Stage 4 (Logstash → ES):     $([ "$ES_RESULT" -gt 0 ] && echo '[✓ PASS]' || echo '[✗ FAIL]')"
echo "=========================================="
echo ""

if [ "$PARSED_COUNT" -gt 0 ] && [ "$NORMALIZED_COUNT" -gt 0 ] && [ "$ES_RESULT" -gt 0 ]; then
    info "✓ PIPELINE TEST PASSED - All stages working!"
    echo ""
    info "To explore the data:"
    echo "  kubectl port-forward -n umbrella-storage svc/elasticsearch 9200:9200"
    echo "  curl http://localhost:9200/messages-*/_search?pretty"
    echo ""
    info "To view logs:"
    echo "  kubectl logs -n umbrella-connectors -l app=email-processor -f"
    echo "  kubectl logs -n umbrella-ingestion -l app=ingestion-service -f"
    echo "  kubectl logs -n umbrella-storage -l app=logstash -f"
    exit 0
else
    error "✗ PIPELINE TEST FAILED - Check logs for errors"
    echo ""
    error "Debugging steps:"
    echo "  kubectl logs -n umbrella-connectors -l app=email-processor --tail=50"
    echo "  kubectl logs -n umbrella-ingestion -l app=ingestion-service --tail=50"
    echo "  kubectl logs -n umbrella-storage -l app=logstash --tail=50"
    exit 1
fi
