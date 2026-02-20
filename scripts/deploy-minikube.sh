#!/usr/bin/env bash
# Deploy Umbrella to minikube.
#
# Builds all Docker images and deploys the full cluster:
#   - Kafka (umbrella-streaming)
#   - PostgreSQL + Flyway migrations (umbrella-storage)
#   - MinIO, Elasticsearch, Logstash, Kibana (umbrella-storage)
#   - Mailserver, email-connector, email-processor (umbrella-connectors)
#   - Ingestion service (umbrella-ingestion)
#   - UI backend + frontend (umbrella-ui)
#
# After this script completes, run scripts/test-pipeline-minikube.sh to
# create DB roles, seed data, and verify the end-to-end pipeline.
#
# NOTE: This script skips optional monitoring resources (PodMonitor, ServiceMonitor)
# that require Prometheus Operator.
# Re-exec under bash if invoked with sh/dash
[ -z "$BASH_VERSION" ] && exec bash "$0" "$@"

set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

echo "=========================================="
echo "Umbrella Deploy - Minikube"
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

# 3. Build all service images (--no-cache ensures code changes are picked up)
info "Building Docker images..."
docker build --no-cache -f connectors/email/Dockerfile -t umbrella-email:latest .
docker build --no-cache -f ingestion-api/Dockerfile -t umbrella-ingestion:latest .
docker build --no-cache -f ui/backend/Dockerfile -t umbrella-ui-backend:latest .
docker build --no-cache -f ui/frontend/Dockerfile -t umbrella-ui-frontend:latest .

# 4. Deploy Kafka
info "Deploying umbrella-streaming (Kafka)..."
kubectl apply -f deploy/k8s/umbrella-streaming/namespace.yaml
for file in deploy/k8s/umbrella-streaming/*.yaml; do
    if [[ "$file" != *"namespace.yaml" ]] && [[ "$file" != *"podmonitor.yaml" ]]; then
        kubectl apply -f "$file"
    fi
done
info "Waiting for Kafka to be ready..."
kubectl rollout status statefulset/kafka -n umbrella-streaming --timeout=180s

# 5. Deploy PostgreSQL + run Flyway migrations
info "Deploying umbrella-storage namespace..."
kubectl apply -f deploy/k8s/umbrella-storage/namespace.yaml

info "Deploying PostgreSQL..."
# Delete old migration Job — K8s Jobs are immutable once completed,
# so we must recreate to pick up new migration versions.
kubectl delete job/postgresql-migrations -n umbrella-storage --ignore-not-found
kubectl apply -f deploy/k8s/umbrella-storage/postgresql/
kubectl rollout status statefulset/postgresql -n umbrella-storage --timeout=180s

# Clear any previously-failed migration records from Flyway's schema history
# table. Equivalent to `flyway repair` — removes rows where success=false so
# Flyway will retry those versions on the next run. No-op on a clean DB.
info "Clearing failed Flyway migration records (if any)..."
PG_POD=$(kubectl get pod -n umbrella-storage -l app=postgresql -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
if [ -n "$PG_POD" ]; then
    kubectl exec -n umbrella-storage "$PG_POD" -- \
        psql -U postgres -d umbrella -c \
        "DELETE FROM public.flyway_schema_history WHERE success = false;" \
        2>/dev/null || true
fi

info "Waiting for PostgreSQL migrations to complete..."
if ! kubectl wait --for=condition=complete job/postgresql-migrations -n umbrella-storage --timeout=300s; then
    error "Migration job did not complete within 300s. Dumping diagnostics..."
    echo ""
    kubectl describe job/postgresql-migrations -n umbrella-storage 2>/dev/null || true
    echo ""
    error "Logs from migration pods:"
    for pod in $(kubectl get pod -n umbrella-storage -l job-name=postgresql-migrations \
            -o jsonpath='{.items[*].metadata.name}' 2>/dev/null); do
        error "--- Pod: $pod ---"
        kubectl logs -n umbrella-storage "$pod" --all-containers=true 2>/dev/null || true
    done
    exit 1
fi

# 6. Deploy MinIO, Elasticsearch, Logstash, Kibana
info "Deploying MinIO..."
kubectl apply -f deploy/k8s/umbrella-storage/minio/
kubectl rollout status deployment/minio -n umbrella-storage --timeout=120s

info "Deploying Elasticsearch..."
kubectl apply -f deploy/k8s/umbrella-storage/elasticsearch/
kubectl rollout status statefulset/elasticsearch -n umbrella-storage --timeout=600s

info "Deploying Logstash..."
kubectl apply -f deploy/k8s/umbrella-storage/logstash/
kubectl rollout status deployment/logstash -n umbrella-storage --timeout=600s

info "Deploying Kibana..."
kubectl apply -f deploy/k8s/umbrella-storage/kibana/
kubectl rollout status deployment/kibana -n umbrella-storage --timeout=300s

# 7. Deploy mailserver (SMTP/IMAP)
info "Deploying mailserver..."
kubectl apply -f deploy/k8s/umbrella-connectors/namespace.yaml
kubectl apply -f deploy/k8s/umbrella-connectors/mailserver-deployment.yaml
info "Waiting for mailserver to be ready..."
kubectl rollout status deployment/mailserver -n umbrella-connectors --timeout=300s

# 8. Deploy pipeline services
info "Deploying email-processor (Stage 2)..."
kubectl apply -f deploy/k8s/umbrella-connectors/email-processor-deployment.yaml
kubectl rollout restart deployment/email-processor -n umbrella-connectors
kubectl wait --for=condition=ready pod -l app=email-processor -n umbrella-connectors --timeout=300s

info "Deploying email-connector (Stage 1)..."
kubectl apply -f deploy/k8s/umbrella-connectors/email-connector-deployment.yaml
kubectl rollout restart deployment/email-connector -n umbrella-connectors
kubectl wait --for=condition=ready pod -l app=email-connector -n umbrella-connectors --timeout=300s

info "Deploying ingestion-service (Stage 3)..."
kubectl apply -f deploy/k8s/umbrella-ingestion/namespace.yaml
kubectl apply -f deploy/k8s/umbrella-ingestion/
kubectl rollout restart deployment/ingestion-service -n umbrella-ingestion
kubectl wait --for=condition=ready pod -l app=ingestion-service -n umbrella-ingestion --timeout=120s

# 9. Deploy UI
info "Deploying umbrella-ui (backend + frontend)..."
kubectl apply -f deploy/k8s/umbrella-ui/namespace.yaml
kubectl apply -f deploy/k8s/umbrella-ui/secret.yaml
kubectl apply -f deploy/k8s/umbrella-ui/backend/
kubectl apply -f deploy/k8s/umbrella-ui/frontend/
kubectl apply -f deploy/k8s/umbrella-ui/ingress.yaml

# Force pod restarts so new :latest images are picked up
kubectl rollout restart deployment/umbrella-ui-backend -n umbrella-ui
kubectl rollout restart deployment/umbrella-ui-frontend -n umbrella-ui

info "Waiting for UI backend to be ready..."
kubectl rollout status deployment/umbrella-ui-backend -n umbrella-ui --timeout=120s

info "Waiting for UI frontend to be ready..."
kubectl rollout status deployment/umbrella-ui-frontend -n umbrella-ui --timeout=60s

echo ""
echo "=========================================="
info "Cluster deployed successfully!"
echo "=========================================="
echo ""
info "Next step: run scripts/test-pipeline-minikube.sh to create DB roles,"
info "seed test data, and verify the end-to-end pipeline."
echo ""
info "Quick access:"
echo "  kubectl port-forward -n umbrella-ui svc/umbrella-ui-frontend 3000:80"
echo "  kubectl port-forward -n umbrella-ui svc/umbrella-ui-backend 8001:8000"
echo "  kubectl port-forward -n umbrella-storage svc/kibana 5601:5601"
