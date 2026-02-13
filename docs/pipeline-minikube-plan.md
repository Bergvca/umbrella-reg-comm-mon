# Plan: Setup and Test Full Pipeline in Minikube — Email Connector → Elasticsearch

## Context

The Umbrella platform has a multi-stage pipeline:

```
Email (IMAP) → S3 + Kafka(raw-messages) → EmailProcessor → Kafka(parsed-messages)
    → IngestionService → Kafka(normalized-messages) → Logstash → Elasticsearch
```

Individual components exist but have never run together. Several infrastructure gaps prevent a working end-to-end pipeline. This plan deploys everything to minikube and tests it.

---

## Current State

### K8s manifests that EXIST:
| Component | Location | Namespace |
|---|---|---|
| Kafka StatefulSet + Services + topic Job | `deploy/k8s/umbrella-streaming/` | `umbrella-streaming` |
| ES StatefulSet + Services + init Job | `deploy/k8s/umbrella-storage/elasticsearch/` | `umbrella-storage` |
| Logstash Deployment + Service + ConfigMaps | `deploy/k8s/umbrella-storage/logstash/` | `umbrella-storage` |

### What is MISSING:

1. **MinIO (S3) K8s manifests** — `infrastructure/s3/.gitkeep` is empty. Email connector, processor, and ingestion service all need S3.

2. **Dockerfiles for Python services** — No Dockerfiles exist for email connector/processor or ingestion service.

3. **K8s manifests for Python services** — `deploy/k8s/umbrella-connectors/`, `deploy/k8s/umbrella-ingestion/` are empty `.gitkeep` stubs.

4. **BaseConnector dual-delivery bug** — `base.py:_deliver()` sends to both Kafka AND HTTP ingestion API in a single retry block. If the HTTP API is unreachable, Kafka delivery also fails → dead-letter. The ingestion service has no HTTP endpoint (`/v1/ingest` doesn't exist). Need to decouple these.

5. **No local IMAP server** — For full Stage 1 testing, need a mock IMAP server or inject test data at `raw-messages` topic.

---

## Implementation Plan

### Step 1: Fix BaseConnector dual-delivery
**Files to modify:**
- `connectors/connector-framework/umbrella_connector/base.py`
- `connectors/connector-framework/umbrella_connector/ingestion_client.py`

Decouple Kafka and HTTP delivery so one doesn't block the other:
```python
# base.py _deliver() — separate paths
async def _deliver(self, message: RawMessage) -> None:
    # Kafka (required, with retry)
    retry_decorator = with_retry(self.config.retry)
    @retry_decorator
    async def _send_kafka() -> None:
        await self._producer.send_raw(message)
    try:
        await _send_kafka()
    except Exception as exc:
        await self._dead_letter.send(message, error=str(exc), ...)
        return

    # HTTP ingestion API (best-effort, skip if disabled)
    try:
        await self._ingestion_client.submit(message)
    except Exception:
        logger.warning("ingestion_api_submit_failed", ...)
```

In `ingestion_client.py`, make `submit()` a no-op when `base_url` is empty:
```python
async def submit(self, message: RawMessage) -> None:
    if self._client is None:
        return  # disabled
    ...
```
And in `start()`, skip client creation when URL is empty/disabled.

Update existing tests to match.

### Step 2: Create MinIO K8s manifests
**Files to create in `deploy/k8s/umbrella-storage/minio/`:**

- `deployment.yaml` — MinIO single-node deployment
  - Image: `minio/minio:latest`
  - Command: `minio server /data --console-address ":9001"`
  - Ports: 9000 (API), 9001 (console)
  - Env: `MINIO_ROOT_USER=minioadmin`, `MINIO_ROOT_PASSWORD=minioadmin`
  - PVC: 5Gi for `/data`
  - Resources: 256Mi request, 512Mi limit

- `service.yaml` — ClusterIP service exposing 9000 + 9001

- `job-create-bucket.yaml` — Init Job using `minio/mc` to create the `umbrella` bucket
  - Waits for MinIO to be ready
  - Runs: `mc alias set local http://minio:9000 ... && mc mb --ignore-existing local/umbrella`

### Step 3: Create Dockerfiles for Python services
**`connectors/email/Dockerfile`:**
```dockerfile
FROM python:3.13-slim
WORKDIR /app
COPY ../connector-framework /app/connector-framework
COPY . /app/email-connector
RUN pip install --no-cache-dir /app/connector-framework /app/email-connector
```
Two entry points via CMD override in K8s manifests: `connector` or `processor` mode.

**`ingestion-api/Dockerfile`:**
```dockerfile
FROM python:3.13-slim
WORKDIR /app
COPY ../connectors/connector-framework /app/connector-framework
COPY . /app/ingestion
RUN pip install --no-cache-dir /app/connector-framework /app/ingestion
CMD ["python", "-m", "umbrella_ingestion"]
```

Note: Since these need the `connector-framework` as a local dependency, the Docker build context must be the project root, and the Dockerfiles will use paths relative to root.

### Step 4: Create K8s manifests for Email Processor
**Files to create in `deploy/k8s/umbrella-connectors/`:**

- `namespace.yaml` — `umbrella-connectors` namespace

- `email-processor-deployment.yaml` — Deployment for Stage 2
  - Image: locally built `umbrella-email:latest`
  - Command: `["python", "-m", "umbrella_email", "processor"]`
  - Env vars:
    - `PROCESSOR_KAFKA_BOOTSTRAP_SERVERS=kafka.umbrella-streaming.svc:9092`
    - `PROCESSOR_SOURCE_TOPIC=raw-messages`
    - `PROCESSOR_OUTPUT_TOPIC=parsed-messages`
    - `S3_BUCKET=umbrella`
    - `S3_ENDPOINT_URL=http://minio.umbrella-storage.svc:9000`
    - `AWS_ACCESS_KEY_ID=minioadmin`
    - `AWS_SECRET_ACCESS_KEY=minioadmin`
  - Health probe on port 8081

### Step 5: Create K8s manifests for Ingestion Service
**Files to create in `deploy/k8s/umbrella-ingestion/`:**

- `namespace.yaml` — `umbrella-ingestion` namespace

- `deployment.yaml` — Deployment for normalization service
  - Image: locally built `umbrella-ingestion:latest`
  - Env vars:
    - `KAFKA_BOOTSTRAP_SERVERS=kafka.umbrella-streaming.svc:9092`
    - `KAFKA_SOURCE_TOPIC=parsed-messages`
    - `KAFKA_OUTPUT_TOPIC=normalized-messages`
    - `S3_BUCKET=umbrella`
    - `S3_ENDPOINT_URL=http://minio.umbrella-storage.svc:9000`
    - `AWS_ACCESS_KEY_ID=minioadmin`
    - `AWS_SECRET_ACCESS_KEY=minioadmin`
    - `INGESTION_MONITORED_DOMAINS=example.com,acme.com`
  - Health probe on port 8082

### Step 6: Create test script for minikube pipeline
**File: `scripts/test-pipeline-minikube.sh`**

```bash
#!/usr/bin/env bash
# End-to-end pipeline test in minikube

# 1. Start minikube (if not running)
minikube start --memory=8192 --cpus=4

# 2. Point Docker to minikube's daemon
eval $(minikube docker-env)

# 3. Build Python service images
docker build -t umbrella-email:latest -f connectors/email/Dockerfile .
docker build -t umbrella-ingestion:latest -f ingestion-api/Dockerfile .

# 4. Deploy infrastructure (order matters — dependencies first)
kubectl apply -f deploy/k8s/umbrella-streaming/namespace.yaml
kubectl apply -f deploy/k8s/umbrella-streaming/
kubectl rollout status statefulset/kafka -n umbrella-streaming --timeout=120s

kubectl apply -f deploy/k8s/umbrella-storage/namespace.yaml
kubectl apply -f deploy/k8s/umbrella-storage/minio/
kubectl apply -f deploy/k8s/umbrella-storage/elasticsearch/
kubectl rollout status statefulset/elasticsearch -n umbrella-storage --timeout=120s

kubectl apply -f deploy/k8s/umbrella-storage/logstash/
kubectl rollout status deployment/logstash -n umbrella-storage --timeout=120s

# 5. Deploy Python services
kubectl apply -f deploy/k8s/umbrella-connectors/
kubectl apply -f deploy/k8s/umbrella-ingestion/

# 6. Wait for all pods ready
kubectl wait --for=condition=ready pod -l app=email-processor -n umbrella-connectors --timeout=120s
kubectl wait --for=condition=ready pod -l app=ingestion-service -n umbrella-ingestion --timeout=120s

# 7. Upload test EML to MinIO
kubectl run mc --image=minio/mc --restart=Never -n umbrella-storage -- \
  sh -c 'mc alias set local http://minio:9000 minioadmin minioadmin && \
  echo "From: alice@example.com\nTo: bob@acme.com\nSubject: Test\nDate: ..." | \
  mc pipe local/umbrella/raw/email/test-001.eml'

# 8. Inject test RawMessage to raw-messages topic
kubectl run kafka-producer --image=apache/kafka:4.1.1 --restart=Never -n umbrella-streaming -- \
  sh -c '/opt/kafka/bin/kafka-console-producer.sh --bootstrap-server kafka:9092 --topic raw-messages <<EOF
{"raw_message_id":"test-001","channel":"email","raw_payload":{"envelope":{"message_id":"test-001","subject":"Test","from":"alice@example.com","to":["bob@acme.com"],"cc":[],"bcc":[],"date":"Thu, 12 Feb 2026 10:00:00 +0000"},"s3_uri":"s3://umbrella/raw/email/test-001.eml","size_bytes":200},"raw_format":"eml_ref","metadata":{"imap_uid":"1","mailbox":"INBOX","imap_host":"test"},"ingested_at":"2026-02-12T10:00:00Z"}
EOF'

# 9. Verify: port-forward and check ES
kubectl port-forward -n umbrella-storage svc/elasticsearch 9200:9200 &
sleep 30  # wait for pipeline to process
curl -s http://localhost:9200/messages-*/_search?pretty | jq .

# 10. Cleanup
# minikube delete
```

### Step 7: Create sample test EML file
**File: `scripts/sample-eml/test-email.eml`**

A valid RFC 822 email with headers + text body + one small attachment for testing the full MIME parsing path.

---

## Files to Create/Modify

| Action | File | Description |
|---|---|---|
| **MODIFY** | `connectors/connector-framework/umbrella_connector/base.py` | Decouple Kafka/HTTP delivery |
| **MODIFY** | `connectors/connector-framework/umbrella_connector/ingestion_client.py` | Add disabled/no-op mode |
| **MODIFY** | `connectors/connector-framework/tests/test_base.py` | Update tests for new delivery logic |
| **MODIFY** | `connectors/connector-framework/tests/test_ingestion_client.py` | Test disabled mode |
| **CREATE** | `deploy/k8s/umbrella-storage/minio/deployment.yaml` | MinIO single-node |
| **CREATE** | `deploy/k8s/umbrella-storage/minio/service.yaml` | MinIO ClusterIP service |
| **CREATE** | `deploy/k8s/umbrella-storage/minio/job-create-bucket.yaml` | Create default bucket |
| **CREATE** | `connectors/email/Dockerfile` | Docker image for email connector + processor |
| **CREATE** | `ingestion-api/Dockerfile` | Docker image for ingestion service |
| **CREATE** | `deploy/k8s/umbrella-connectors/namespace.yaml` | Namespace for connectors |
| **CREATE** | `deploy/k8s/umbrella-connectors/email-processor-deployment.yaml` | Email processor K8s Deployment |
| **CREATE** | `deploy/k8s/umbrella-ingestion/namespace.yaml` | Namespace for ingestion |
| **CREATE** | `deploy/k8s/umbrella-ingestion/deployment.yaml` | Ingestion service K8s Deployment |
| **CREATE** | `scripts/test-pipeline-minikube.sh` | Automated end-to-end test |
| **CREATE** | `scripts/sample-eml/test-email.eml` | Sample email for testing |

---

## Deployment Order in Minikube

```
1. umbrella-streaming   →  Kafka StatefulSet + topic creation Job
2. umbrella-storage     →  MinIO + ES StatefulSet + ES init Job + Logstash
3. umbrella-connectors  →  Email Processor (Stage 2)
4. umbrella-ingestion   →  Ingestion Service (normalizer)
```

## Test Verification

### Test A: Full pipeline (inject at `raw-messages`, skip IMAP)
1. Upload sample EML to MinIO at `s3://umbrella/raw/email/test-001.eml`
2. Produce a `RawMessage` JSON to `raw-messages` topic (referencing the EML in MinIO)
3. **Verify**: Email Processor picks it up → parses EML → produces to `parsed-messages`
4. **Verify**: Ingestion Service picks it up → normalizes → produces to `normalized-messages`
5. **Verify**: Logstash picks it up → indexes into ES `messages-2026.02`
6. **Verify**: `curl http://localhost:9200/messages-*/_search` returns the document

### Test B: Logstash-only (inject at `normalized-messages`)
1. Produce a NormalizedMessage JSON directly to `normalized-messages` topic
2. **Verify**: Document appears in ES

### Test C: Upsert verification
1. Produce a NormalizedMessage to `normalized-messages`
2. Produce an enrichment with same `message_id` to `processing-results`
3. **Verify**: ES document contains merged fields

### Resource Requirements
Minikube should be started with at least:
- **Memory**: 8GB (`--memory=8192`)
- **CPUs**: 4 (`--cpus=4`)
- **Disk**: 20GB (default is usually fine)

---

## Out of Scope (noted as missing)

1. **Processing services** (transcription, translation, NLP) — `processing/` dirs are empty stubs
2. **PostgreSQL** — `infrastructure/postgresql/.gitkeep` is empty (needed for UI, not data pipeline)
3. **UI backend + frontend** — `ui/backend/.gitkeep` and `ui/frontend/.gitkeep` are empty
4. **CI/CD** — No `.github/`, Jenkinsfile, or CI configuration
5. **Monitoring/observability** — No Prometheus/Grafana/OpenTelemetry
6. **Security** — ES security disabled, Kafka no auth, MinIO default creds (dev only)
7. **Email Connector Stage 1** — Needs real or mock IMAP server. Test bypasses it by injecting at `raw-messages`
8. **K8s manifests for remaining connectors** (teams-chat, bloomberg, etc.) — stubs only
