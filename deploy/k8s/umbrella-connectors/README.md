# Umbrella Connectors

Kubernetes deployments for Stage 2 processors that consume raw messages, parse them, and produce structured data.

## Components

### Email Processor

**Stage**: 2 (Raw → Parsed)

**Function**:
- Consumes `RawMessage` from Kafka `raw-messages` topic
- Downloads .eml files from S3 (claim-check pattern)
- Parses MIME structure (headers, body, attachments)
- Uploads attachments to S3
- Produces `ParsedMessage` to Kafka `parsed-messages` topic

**Health**: Port 8081 (`/health`, `/ready`)

## Architecture

```
Kafka(raw-messages) → Email Processor → Kafka(parsed-messages)
                           ↓
                       MinIO (S3)
                  (download .eml, upload attachments)
```

## Dependencies

Must be deployed after:
- `umbrella-streaming` (Kafka)
- `umbrella-storage/minio` (S3)

## Deployment

```bash
# Build the Docker image first (in minikube)
eval $(minikube docker-env)
./scripts/build-images.sh email

# Apply manifests
kubectl apply -f deploy/k8s/umbrella-connectors/namespace.yaml
kubectl apply -f deploy/k8s/umbrella-connectors/email-processor-deployment.yaml

# Wait for processor to be ready
kubectl rollout status deployment/email-processor -n umbrella-connectors

# Check logs
kubectl logs -n umbrella-connectors -l app=email-processor -f

# Check health
kubectl port-forward -n umbrella-connectors svc/email-processor 8081:8081
curl http://localhost:8081/health
```

## Configuration

### Environment Variables

| Variable | Value | Description |
|----------|-------|-------------|
| `PROCESSOR_KAFKA_BOOTSTRAP_SERVERS` | `kafka.umbrella-streaming.svc:9092` | Kafka brokers |
| `PROCESSOR_SOURCE_TOPIC` | `raw-messages` | Input topic |
| `PROCESSOR_OUTPUT_TOPIC` | `parsed-messages` | Output topic |
| `PROCESSOR_CONSUMER_GROUP` | `email-processor` | Consumer group ID |
| `PROCESSOR_HEALTH_PORT` | `8081` | Health check port |
| `S3_BUCKET` | `umbrella` | S3 bucket name |
| `S3_ENDPOINT_URL` | `http://minio.umbrella-storage.svc:9000` | MinIO endpoint |
| `AWS_ACCESS_KEY_ID` | `minioadmin` | S3 credentials (dev) |
| `AWS_SECRET_ACCESS_KEY` | `minioadmin` | S3 credentials (dev) |
| `LOG_LEVEL` | `INFO` | Logging level |
| `LOG_FORMAT` | `json` | Log format |

### Resources

- **Requests**: 256Mi memory, 100m CPU
- **Limits**: 512Mi memory, 500m CPU

### Image

- **Name**: `umbrella-email:latest`
- **Pull Policy**: `Never` (uses local minikube image)
- **Build**: `./scripts/build-images.sh email`

## Scaling

The email processor can be scaled horizontally:

```bash
kubectl scale deployment/email-processor -n umbrella-connectors --replicas=3
```

Kafka consumer group ensures messages are distributed across replicas.

## Troubleshooting

### Pod not starting - ImagePullBackOff

**Cause**: Docker image not found in minikube.

**Solution**:
```bash
eval $(minikube docker-env)
./scripts/build-images.sh email
kubectl rollout restart deployment/email-processor -n umbrella-connectors
```

### Pod crashing - Connection refused (Kafka)

**Cause**: Kafka not ready or wrong bootstrap servers.

**Solution**:
```bash
# Verify Kafka is running
kubectl get pods -n umbrella-streaming

# Check logs for connection errors
kubectl logs -n umbrella-connectors -l app=email-processor --tail=100
```

### Pod crashing - S3 access errors

**Cause**: MinIO not ready or wrong credentials.

**Solution**:
```bash
# Verify MinIO is running
kubectl get pods -n umbrella-storage -l app=minio

# Check MinIO bucket exists
kubectl port-forward -n umbrella-storage svc/minio 9000:9000
# In another terminal:
docker run --rm --network=host minio/mc \
  alias set local http://localhost:9000 minioadmin minioadmin \
  && mc ls local/umbrella
```

### No messages being processed

**Cause**: No messages in `raw-messages` topic.

**Solution**: Inject a test message (see `scripts/test-pipeline-minikube.sh`).

## Future Connectors

This namespace will eventually contain:
- `teams-chat-processor`
- `bloomberg-processor`
- `turret-processor`
- etc.

Each processor follows the same pattern: consume raw → parse → produce parsed.
