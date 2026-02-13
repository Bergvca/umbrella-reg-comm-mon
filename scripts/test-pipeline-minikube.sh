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

msg = EmailMessage()
msg['From'] = 'alice@example.com'
msg['To'] = 'testuser@umbrella.local'
msg['Subject'] = 'Pipeline Test - E2E Validation'
msg['Message-ID'] = '<pipeline-test-001@example.com>'
msg.set_content('Test email for pipeline validation. If this appears in Elasticsearch, all 4 stages work.')

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

echo ""
echo "=========================================="
echo "Pipeline Test Summary"
echo "=========================================="
echo "Stage 1 (IMAP Connector):    $([ "$RAW_COUNT" -gt 0 ] && echo '[✓ PASS]' || echo '[✗ FAIL]')"
echo "Stage 2 (Email Processor):   $([ "$PARSED_COUNT" -gt 0 ] && echo '[✓ PASS]' || echo '[✗ FAIL]')"
echo "Stage 3 (Ingestion Service): $([ "$NORMALIZED_COUNT" -gt 0 ] && echo '[✓ PASS]' || echo '[✗ FAIL]')"
echo "Stage 4 (Logstash → ES):     $([ "$ES_RESULT" -gt 0 ] && echo '[✓ PASS]' || echo '[✗ FAIL]')"
echo "=========================================="
echo ""

if [ "$RAW_COUNT" -gt 0 ] && [ "$PARSED_COUNT" -gt 0 ] && [ "$NORMALIZED_COUNT" -gt 0 ] && [ "$ES_RESULT" -gt 0 ]; then
    info "✓ PIPELINE TEST PASSED - All 4 stages working!"
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
    exit 0
else
    error "✗ PIPELINE TEST FAILED - Check logs for errors"
    echo ""
    error "Debugging steps:"
    echo "  kubectl logs -n umbrella-connectors -l app=email-connector --tail=50"
    echo "  kubectl logs -n umbrella-connectors -l app=email-processor --tail=50"
    echo "  kubectl logs -n umbrella-ingestion -l app=ingestion-service --tail=50"
    echo "  kubectl logs -n umbrella-storage -l app=logstash --tail=50"
    exit 1
fi
