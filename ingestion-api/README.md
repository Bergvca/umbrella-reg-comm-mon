# Ingestion Service

Stage 3 of the Umbrella pipeline: normalize parsed messages into canonical schema.

## Architecture

- Consumes `ParsedMessage` from Kafka `parsed-messages` topic
- Applies channel-specific normalizers (email, teams, bloomberg, etc.)
- Produces `NormalizedMessage` to Kafka `normalized-messages` topic
- Dual-writes to S3 for backup/replay

## Normalization

Each channel has a dedicated normalizer in `umbrella_ingestion/normalizers/`:

- `EmailNormalizer` - Email messages
- `TeamsChatNormalizer` - Teams chat messages
- `BloombergNormalizer` - Bloomberg messages
- etc.

All normalizers extend `BaseNormalizer` and implement `normalize()`.

## Running Locally

### Prerequisites
- Kafka running on localhost:9092
- MinIO/S3 accessible
- Python 3.11+

### Install
```bash
pip install -e ../connectors/connector-framework -e .
```

### Run
```bash
export KAFKA_BOOTSTRAP_SERVERS=localhost:9092
export KAFKA_SOURCE_TOPIC=parsed-messages
export KAFKA_OUTPUT_TOPIC=normalized-messages
export S3_BUCKET=umbrella
export S3_ENDPOINT_URL=http://localhost:9000
export AWS_ACCESS_KEY_ID=minioadmin
export AWS_SECRET_ACCESS_KEY=minioadmin
export INGESTION_MONITORED_DOMAINS=example.com,acme.com

python -m umbrella_ingestion
```

## Docker

### Build
```bash
# From repository root
docker build -t umbrella-ingestion:latest -f ingestion-api/Dockerfile .
```

### Run
```bash
docker run --rm \
  -e KAFKA_BOOTSTRAP_SERVERS=kafka:9092 \
  -e KAFKA_SOURCE_TOPIC=parsed-messages \
  -e KAFKA_OUTPUT_TOPIC=normalized-messages \
  -e S3_BUCKET=umbrella \
  -e S3_ENDPOINT_URL=http://minio:9000 \
  -e AWS_ACCESS_KEY_ID=minioadmin \
  -e AWS_SECRET_ACCESS_KEY=minioadmin \
  -e INGESTION_MONITORED_DOMAINS=example.com,acme.com \
  umbrella-ingestion:latest
```

## Kubernetes

See `deploy/k8s/umbrella-ingestion/deployment.yaml`

## Configuration

Environment variables:

- `KAFKA_BOOTSTRAP_SERVERS` - Kafka brokers
- `KAFKA_SOURCE_TOPIC` - Input topic (default: `parsed-messages`)
- `KAFKA_OUTPUT_TOPIC` - Output topic (default: `normalized-messages`)
- `S3_BUCKET` - S3 bucket name
- `S3_ENDPOINT_URL` - S3 endpoint (for MinIO)
- `AWS_ACCESS_KEY_ID` - S3 credentials
- `AWS_SECRET_ACCESS_KEY` - S3 credentials
- `INGESTION_MONITORED_DOMAINS` - Comma-separated domains to monitor

## Testing

```bash
pytest tests/ -v
```

## Dependencies

- `umbrella-connector-framework` - Base infrastructure (Kafka, logging, etc.)
- `boto3` - S3 access for dual-write pattern
- `umbrella-schema` - Canonical message schema
