# Minikube Deployment Guide

Complete guide for deploying and testing the full Umbrella pipeline in minikube.

## Overview

The Umbrella pipeline consists of 4 stages:

```
Stage 1: IMAP → S3 + Kafka (raw-messages)           [email-connector - NOT YET DEPLOYED]
Stage 2: Kafka → Parse EML → Kafka (parsed-messages) [email-processor]
Stage 3: Kafka → Normalize → Kafka (normalized-messages) [ingestion-service]
Stage 4: Kafka → Logstash → Elasticsearch            [logstash]
```

This guide covers deploying Stages 2-4 and testing the pipeline end-to-end.

## Prerequisites

### Required Tools

- **minikube** (v1.30+)
- **kubectl** (v1.26+)
- **Docker** (v20.10+)
- **bash** (v4.0+)

### System Requirements

- **Memory**: 8GB minimum (recommend 16GB)
- **CPU**: 4 cores minimum
- **Disk**: 20GB free space

### Install Tools

```bash
# macOS (using Homebrew)
brew install minikube kubectl docker

# Linux
curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
sudo install minikube-linux-amd64 /usr/local/bin/minikube

# Verify installations
minikube version
kubectl version --client
docker --version
```

## Quick Start (Automated)

The fastest way to deploy and test the pipeline:

```bash
# 1. Clone the repository
cd /path/to/regcommon

# 2. Run the automated test script
./scripts/test-pipeline-minikube.sh
```

This script will:
1. Start minikube (if not running)
2. Build all Docker images
3. Deploy all infrastructure and services
4. Inject a test message
5. Verify the message flows through all stages
6. Report results

**Expected output**: All stages should show `[✓ PASS]`

## Manual Deployment (Step-by-Step)

### Step 1: Start Minikube

```bash
# Start with sufficient resources
minikube start --memory=8192 --cpus=4

# Verify
minikube status
```

### Step 2: Build Docker Images

```bash
# Point Docker to minikube's daemon
eval $(minikube docker-env)

# Build all images
./scripts/build-images.sh

# Verify images
docker images | grep umbrella
# Should see: umbrella-email:latest and umbrella-ingestion:latest
```

### Step 3: Deploy Infrastructure

Deploy in order (dependencies first):

#### 3a. Kafka (umbrella-streaming)

```bash
kubectl apply -f deploy/k8s/umbrella-streaming/namespace.yaml
kubectl apply -f deploy/k8s/umbrella-streaming/

# Wait for Kafka
kubectl rollout status statefulset/kafka -n umbrella-streaming --timeout=180s

# Verify
kubectl get pods -n umbrella-streaming
# Should see: kafka-0 (Running)
```

#### 3b. Storage (umbrella-storage)

```bash
kubectl apply -f deploy/k8s/umbrella-storage/namespace.yaml

# Deploy MinIO
kubectl apply -f deploy/k8s/umbrella-storage/minio/
kubectl rollout status deployment/minio -n umbrella-storage

# Deploy Elasticsearch
kubectl apply -f deploy/k8s/umbrella-storage/elasticsearch/
kubectl rollout status statefulset/elasticsearch -n umbrella-storage

# Deploy Logstash
kubectl apply -f deploy/k8s/umbrella-storage/logstash/
kubectl rollout status deployment/logstash -n umbrella-storage

# Verify
kubectl get pods -n umbrella-storage
# Should see: minio-xxx, elasticsearch-0, logstash-xxx (all Running)
```

### Step 4: Deploy Processing Services

#### 4a. Email Processor (umbrella-connectors)

```bash
kubectl apply -f deploy/k8s/umbrella-connectors/namespace.yaml
kubectl apply -f deploy/k8s/umbrella-connectors/email-processor-deployment.yaml

# Wait for processor
kubectl wait --for=condition=ready pod -l app=email-processor -n umbrella-connectors --timeout=120s

# Verify
kubectl get pods -n umbrella-connectors
# Should see: email-processor-xxx (Running)
```

#### 4b. Ingestion Service (umbrella-ingestion)

```bash
kubectl apply -f deploy/k8s/umbrella-ingestion/namespace.yaml
kubectl apply -f deploy/k8s/umbrella-ingestion/deployment.yaml

# Wait for service
kubectl wait --for=condition=ready pod -l app=ingestion-service -n umbrella-ingestion --timeout=120s

# Verify
kubectl get pods -n umbrella-ingestion
# Should see: ingestion-service-xxx (Running)
```

### Step 5: Verify All Services

```bash
# Check all pods
kubectl get pods --all-namespaces | grep umbrella

# Expected:
# umbrella-streaming     kafka-0                    1/1  Running
# umbrella-storage       minio-xxx                  1/1  Running
# umbrella-storage       elasticsearch-0            1/1  Running
# umbrella-storage       logstash-xxx               1/1  Running
# umbrella-connectors    email-processor-xxx        1/1  Running
# umbrella-ingestion     ingestion-service-xxx      1/1  Running
```

## Testing the Pipeline

### Automated Test

```bash
./scripts/test-pipeline-minikube.sh
```

### Manual Test

#### 1. Upload Test EML to MinIO

```bash
# Use sample EML
kubectl run mc --rm -i --image=minio/mc -n umbrella-storage -- \
  sh -c "mc alias set local http://minio:9000 minioadmin minioadmin && \
         mc mb --ignore-existing local/umbrella/raw/email && \
         cat | mc pipe local/umbrella/raw/email/test.eml" \
  < scripts/sample-eml/test-email.eml
```

#### 2. Inject RawMessage to Kafka

```bash
# Create message JSON
cat > /tmp/raw-message.json <<EOF
{
  "raw_message_id": "manual-test-001",
  "channel": "email",
  "raw_payload": {
    "envelope": {
      "message_id": "<20260212143520.12345@example.com>",
      "subject": "Test Email",
      "from": "alice@example.com",
      "to": ["bob@acme.com"],
      "cc": [],
      "bcc": [],
      "date": "$(date -Iseconds)"
    },
    "s3_uri": "s3://umbrella/raw/email/test.eml",
    "size_bytes": 3000
  },
  "raw_format": "eml_ref",
  "metadata": {},
  "ingested_at": "$(date -Iseconds)"
}
EOF

# Produce to Kafka
kubectl run kafka-producer --rm -i --image=apache/kafka:4.1.1 -n umbrella-streaming -- \
  /opt/kafka/bin/kafka-console-producer.sh \
  --bootstrap-server kafka:9092 \
  --topic raw-messages < /tmp/raw-message.json
```

#### 3. Verify Message Flow

**Check parsed-messages topic:**
```bash
kubectl run kafka-consumer --rm -i --image=apache/kafka:4.1.1 -n umbrella-streaming -- \
  /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server kafka:9092 \
  --topic parsed-messages \
  --from-beginning \
  --max-messages 1
```

**Check normalized-messages topic:**
```bash
kubectl run kafka-consumer --rm -i --image=apache/kafka:4.1.1 -n umbrella-streaming -- \
  /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server kafka:9092 \
  --topic normalized-messages \
  --from-beginning \
  --max-messages 1
```

**Check Elasticsearch:**
```bash
kubectl port-forward -n umbrella-storage svc/elasticsearch 9200:9200 &
sleep 5
curl http://localhost:9200/messages-*/_search?pretty | jq '.hits.hits[]'
```

## Viewing Logs

### Service Logs

```bash
# Email processor
kubectl logs -n umbrella-connectors -l app=email-processor -f

# Ingestion service
kubectl logs -n umbrella-ingestion -l app=ingestion-service -f

# Logstash
kubectl logs -n umbrella-storage -l app=logstash -f

# Kafka
kubectl logs -n umbrella-streaming kafka-0 -f
```

### Error Logs Only

```bash
# Show only errors from all services
kubectl logs -n umbrella-connectors -l app=email-processor | grep -i error
kubectl logs -n umbrella-ingestion -l app=ingestion-service | grep -i error
kubectl logs -n umbrella-storage -l app=logstash | grep -i error
```

## Accessing Services

### Port Forwarding

```bash
# Elasticsearch
kubectl port-forward -n umbrella-storage svc/elasticsearch 9200:9200

# MinIO Console
kubectl port-forward -n umbrella-storage svc/minio 9001:9001

# Kafka (bootstrap)
kubectl port-forward -n umbrella-streaming svc/kafka 9092:9092

# Email Processor Health
kubectl port-forward -n umbrella-connectors svc/email-processor 8081:8081

# Ingestion Service Health
kubectl port-forward -n umbrella-ingestion svc/ingestion-service 8082:8082
```

### Web UIs

**MinIO Console**: http://localhost:9001
- Username: `minioadmin`
- Password: `minioadmin`

**Elasticsearch**: http://localhost:9200
- No authentication (dev mode)

## Troubleshooting

### PodMonitor / ServiceMonitor CRD Errors

**Error**: `no matches for kind "PodMonitor" in version "monitoring.coreos.com/v1"`

**Cause**: Optional monitoring resources require Prometheus Operator, which isn't installed by default.

**Solution**: These resources are optional and can be safely skipped. The test script automatically excludes them. If manually deploying:

```bash
# Skip podmonitor.yaml when applying
kubectl apply -f deploy/k8s/umbrella-streaming/namespace.yaml
for file in deploy/k8s/umbrella-streaming/*.yaml; do
    if [[ "$file" != *"podmonitor.yaml" ]]; then
        kubectl apply -f "$file"
    fi
done
```

To use monitoring resources, install Prometheus Operator first:
```bash
kubectl apply -f https://raw.githubusercontent.com/prometheus-operator/prometheus-operator/main/bundle.yaml
```

### Pods Not Starting

**Check events:**
```bash
kubectl get events -n <namespace> --sort-by='.lastTimestamp'
```

**Check pod details:**
```bash
kubectl describe pod <pod-name> -n <namespace>
```

### ImagePullBackOff

**Cause**: Docker image not available in minikube.

**Solution**:
```bash
eval $(minikube docker-env)
./scripts/build-images.sh
kubectl rollout restart deployment/<deployment-name> -n <namespace>
```

### CrashLoopBackOff

**Check logs for errors:**
```bash
kubectl logs <pod-name> -n <namespace> --previous
```

Common causes:
- Kafka not ready: Wait for Kafka StatefulSet
- MinIO not ready: Check MinIO pod status
- Configuration error: Check environment variables

### No Messages Processed

1. **Check Kafka topics exist:**
```bash
kubectl run kafka-topics --rm -i --image=apache/kafka:4.1.1 -n umbrella-streaming -- \
  /opt/kafka/bin/kafka-topics.sh \
  --bootstrap-server kafka:9092 \
  --list
```

2. **Check consumer lag:**
```bash
kubectl run kafka-consumer-groups --rm -i --image=apache/kafka:4.1.1 -n umbrella-streaming -- \
  /opt/kafka/bin/kafka-consumer-groups.sh \
  --bootstrap-server kafka:9092 \
  --describe \
  --group email-processor
```

3. **Check dead-letter topics:**
```bash
# Check for failed messages
kubectl run kafka-consumer --rm -i --image=apache/kafka:4.1.1 -n umbrella-streaming -- \
  /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server kafka:9092 \
  --topic dead-letter \
  --from-beginning \
  --max-messages 10
```

## Cleanup

### Delete All Resources

```bash
# Delete namespaces (cascades to all resources)
kubectl delete namespace umbrella-streaming
kubectl delete namespace umbrella-storage
kubectl delete namespace umbrella-connectors
kubectl delete namespace umbrella-ingestion

# Or delete minikube entirely
minikube delete
```

### Restart Fresh

```bash
# Delete and restart
minikube delete
minikube start --memory=8192 --cpus=4

# Redeploy
./scripts/test-pipeline-minikube.sh
```

## Performance Tuning

### Increase Resources

```bash
# Stop minikube
minikube stop

# Reconfigure
minikube config set memory 16384
minikube config set cpus 6

# Restart
minikube start
```

### Scale Services

```bash
# Scale email processor
kubectl scale deployment/email-processor -n umbrella-connectors --replicas=3

# Scale ingestion service
kubectl scale deployment/ingestion-service -n umbrella-ingestion --replicas=2
```

## Next Steps

After successful deployment:

1. **Add more channels**: Deploy teams-chat, bloomberg processors
2. **Add processing services**: Transcription, translation, NLP
3. **Add UI**: Deploy frontend and backend services
4. **Production setup**: Move to real K8s cluster with proper resources

## References

- [Pipeline Plan](../docs/pipeline-minikube-plan.md)
- [Docker Images](./docker-images.md)
- [Sample EML Files](../scripts/sample-eml/README.md)
- Individual service READMEs:
  - [Email Processor](../connectors/email/README.md)
  - [Ingestion Service](../ingestion-api/README.md)
