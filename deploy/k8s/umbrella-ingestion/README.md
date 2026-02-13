# Umbrella Ingestion Service

Kubernetes deployment for Stage 3: Normalization service that transforms parsed messages into canonical schema.

## Components

### Ingestion Service

**Stage**: 3 (Parsed → Normalized)

**Function**:
- Consumes `ParsedMessage` from Kafka `parsed-messages` topic
- Applies channel-specific normalizers (email, teams, bloomberg, etc.)
- Produces `NormalizedMessage` to Kafka `normalized-messages` topic
- Dual-writes to S3 for backup/replay
- Handles failed messages via dead-letter queue

**Health**: Port 8082 (`/health`, `/ready`)
**API**: Port 8000 (optional, for future HTTP endpoints)

## Architecture

```
Kafka(parsed-messages) → Ingestion Service → Kafka(normalized-messages) → Logstash → Elasticsearch
                              ↓
                          MinIO (S3)
                   (backup normalized messages)
```

## Normalization

Each channel has a dedicated normalizer:

| Channel | Normalizer | Status |
|---------|------------|--------|
| Email | `EmailNormalizer` | ✓ Implemented |
| Teams Chat | `TeamsChatNormalizer` | Stub |
| Bloomberg | `BloombergNormalizer` | Stub |
| Turret | `TurretNormalizer` | Stub |

All normalizers:
- Extend `BaseNormalizer` abstract class
- Implement `normalize(ParsedMessage) -> NormalizedMessage`
- Registered in `NormalizerRegistry`

## Dependencies

Must be deployed after:
- `umbrella-streaming` (Kafka)
- `umbrella-storage/minio` (S3)
- `umbrella-connectors/email-processor` (produces parsed messages)

## Deployment

```bash
# Build the Docker image first (in minikube)
eval $(minikube docker-env)
./scripts/build-images.sh ingestion

# Apply manifests
kubectl apply -f deploy/k8s/umbrella-ingestion/namespace.yaml
kubectl apply -f deploy/k8s/umbrella-ingestion/deployment.yaml

# Wait for service to be ready
kubectl rollout status deployment/ingestion-service -n umbrella-ingestion

# Check logs
kubectl logs -n umbrella-ingestion -l app=ingestion-service -f

# Check health
kubectl port-forward -n umbrella-ingestion svc/ingestion-service 8082:8082
curl http://localhost:8082/health
```

## Configuration

### Environment Variables

#### Kafka Configuration (KAFKA_ prefix)

| Variable | Value | Description |
|----------|-------|-------------|
| `KAFKA_BOOTSTRAP_SERVERS` | `kafka.umbrella-streaming.svc:9092` | Kafka brokers |
| `KAFKA_SOURCE_TOPIC` | `parsed-messages` | Input topic |
| `KAFKA_OUTPUT_TOPIC` | `normalized-messages` | Output topic |
| `KAFKA_CONSUMER_GROUP` | `ingestion-normalizer` | Consumer group ID |
| `KAFKA_DEAD_LETTER_TOPIC` | `normalized-messages-dlq` | Failed messages |
| `KAFKA_PRODUCER_ACKS` | `all` | Producer acknowledgement |
| `KAFKA_PRODUCER_COMPRESSION` | `gzip` | Message compression |

#### S3 Configuration (S3_ prefix)

| Variable | Value | Description |
|----------|-------|-------------|
| `S3_BUCKET` | `umbrella` | S3 bucket name |
| `S3_PREFIX` | `normalized` | Key prefix for normalized messages |
| `S3_ENDPOINT_URL` | `http://minio.umbrella-storage.svc:9000` | MinIO endpoint |
| `S3_REGION` | `us-east-1` | AWS region |
| `AWS_ACCESS_KEY_ID` | `minioadmin` | S3 credentials (dev) |
| `AWS_SECRET_ACCESS_KEY` | `minioadmin` | S3 credentials (dev) |

#### Ingestion Configuration (INGESTION_ prefix)

| Variable | Value | Description |
|----------|-------|-------------|
| `INGESTION_HEALTH_PORT` | `8082` | Health check port |
| `INGESTION_API_PORT` | `8000` | API server port (future use) |
| `INGESTION_MONITORED_DOMAINS` | `example.com,acme.com` | Org domains for direction detection |

#### Logging

| Variable | Value | Description |
|----------|-------|-------------|
| `LOG_LEVEL` | `INFO` | Logging level |
| `LOG_FORMAT` | `json` | Log format (json/console) |

### Monitored Domains

The `INGESTION_MONITORED_DOMAINS` setting is a comma-separated list of email domains owned by your organization. This is used to determine message direction:

- **INTERNAL**: Both sender and recipient are in monitored domains
- **INBOUND**: External sender → monitored domain recipient
- **OUTBOUND**: Monitored domain sender → external recipient
- **EXTERNAL**: Neither sender nor recipient in monitored domains

Example:
```yaml
- name: INGESTION_MONITORED_DOMAINS
  value: acme.com,acme.co.uk,acme-group.com
```

### Resources

- **Requests**: 256Mi memory, 100m CPU
- **Limits**: 512Mi memory, 500m CPU

### Image

- **Name**: `umbrella-ingestion:latest`
- **Pull Policy**: `Never` (uses local minikube image)
- **Build**: `./scripts/build-images.sh ingestion`

## Scaling

The ingestion service can be scaled horizontally:

```bash
kubectl scale deployment/ingestion-service -n umbrella-ingestion --replicas=3
```

Kafka consumer group ensures messages are distributed across replicas.

## Monitoring

### Health Endpoints

- **`/health`**: Service liveness (port 8082)
- **`/ready`**: Service readiness (port 8082)

### Metrics (Future)

The service is instrumented for metrics collection:
- Message processing rate
- Normalization errors
- S3 write latency
- Kafka consumer lag

## Troubleshooting

### Pod not starting - ImagePullBackOff

**Cause**: Docker image not found in minikube.

**Solution**:
```bash
eval $(minikube docker-env)
./scripts/build-images.sh ingestion
kubectl rollout restart deployment/ingestion-service -n umbrella-ingestion
```

### Pod crashing - Connection refused (Kafka)

**Cause**: Kafka not ready or wrong bootstrap servers.

**Solution**:
```bash
# Verify Kafka is running
kubectl get pods -n umbrella-streaming

# Check logs for connection errors
kubectl logs -n umbrella-ingestion -l app=ingestion-service --tail=100
```

### Pod crashing - S3 access errors

**Cause**: MinIO not ready or wrong credentials.

**Solution**:
```bash
# Verify MinIO is running
kubectl get pods -n umbrella-storage -l app=minio

# Check S3 bucket exists
kubectl run mc --rm -i --image=minio/mc -n umbrella-storage -- \
  sh -c 'mc alias set local http://minio:9000 minioadmin minioadmin && mc ls local/umbrella'
```

### No messages being processed

**Cause**: No messages in `parsed-messages` topic.

**Solution**:
1. Verify email-processor is running and processing
2. Check if there are messages in `raw-messages` topic
3. Inject a test message to `parsed-messages`

### Normalization errors in logs

**Cause**: Invalid parsed message format or normalizer bug.

**Solution**:
```bash
# Check dead-letter topic
kubectl run kafka-consumer --rm -i --image=apache/kafka:4.1.1 -n umbrella-streaming -- \
  /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server kafka:9092 \
  --topic normalized-messages-dlq \
  --from-beginning \
  --max-messages 10
```

## Data Flow

### Success Path

1. Consume `ParsedMessage` from `parsed-messages` topic
2. Lookup normalizer for channel (e.g., `EmailNormalizer`)
3. Transform to `NormalizedMessage` (canonical schema)
4. Write to S3 (`s3://umbrella/normalized/YYYY-MM-DD/...`)
5. Produce to `normalized-messages` topic
6. Commit Kafka offset

### Error Path

1. Normalization fails (e.g., invalid data, normalizer bug)
2. Log error with full context
3. Send to dead-letter topic (`normalized-messages-dlq`)
4. Commit Kafka offset (don't retry indefinitely)

### Dead Letter Handling (Future)

Dead-lettered messages can be:
- Replayed after fixing normalizer bugs
- Analyzed for data quality issues
- Archived for compliance

## Adding New Normalizers

To add support for a new channel:

1. Create normalizer class in `umbrella_ingestion/normalizers/`:
   ```python
   class MyChannelNormalizer(BaseNormalizer):
       def normalize(self, parsed: ParsedMessage) -> NormalizedMessage:
           # Transform logic here
           ...
   ```

2. Register in `NormalizerRegistry`:
   ```python
   registry.register(Channel.MY_CHANNEL, MyChannelNormalizer())
   ```

3. No K8s changes needed - just rebuild the image:
   ```bash
   eval $(minikube docker-env)
   ./scripts/build-images.sh ingestion
   kubectl rollout restart deployment/ingestion-service -n umbrella-ingestion
   ```

## Testing

### Unit Tests
```bash
cd ingestion-api
pytest tests/ -v
```

### Integration Test
```bash
# Inject a parsed message
kubectl run kafka-producer --rm -i --image=apache/kafka:4.1.1 -n umbrella-streaming -- \
  /opt/kafka/bin/kafka-console-producer.sh \
  --bootstrap-server kafka:9092 \
  --topic parsed-messages < test-parsed-message.json

# Watch logs for normalization
kubectl logs -n umbrella-ingestion -l app=ingestion-service -f

# Check normalized-messages topic
kubectl run kafka-consumer --rm -i --image=apache/kafka:4.1.1 -n umbrella-streaming -- \
  /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server kafka:9092 \
  --topic normalized-messages \
  --from-beginning \
  --max-messages 1
```
