# Email Connector

Two-stage email ingestion using IMAP and the claim-check pattern.

## Architecture

### Stage 1: IMAP Connector
- Polls IMAP mailbox for new messages
- Stores full .eml files in S3
- Publishes `RawMessage` (with S3 reference) to Kafka `raw-messages` topic

### Stage 2: Email Processor
- Consumes from Kafka `raw-messages` topic
- Downloads .eml from S3
- Parses MIME structure (headers, body, attachments)
- Publishes structured `ParsedMessage` to Kafka `parsed-messages` topic

## Running Locally

### Prerequisites
- Kafka running on localhost:9092
- MinIO/S3 accessible
- Python 3.11+

### Install
```bash
pip install -e ../connector-framework -e .
```

### Stage 1: IMAP Connector
```bash
export CONNECTOR_NAME=email-connector
export KAFKA_BOOTSTRAP_SERVERS=localhost:9092
export IMAP_HOST=imap.gmail.com
export IMAP_USER=user@example.com
export IMAP_PASSWORD=secret
export S3_BUCKET=umbrella
export S3_ENDPOINT_URL=http://localhost:9000
export AWS_ACCESS_KEY_ID=minioadmin
export AWS_SECRET_ACCESS_KEY=minioadmin

python -m umbrella_email connector
```

### Stage 2: Email Processor
```bash
export PROCESSOR_KAFKA_BOOTSTRAP_SERVERS=localhost:9092
export PROCESSOR_SOURCE_TOPIC=raw-messages
export PROCESSOR_OUTPUT_TOPIC=parsed-messages
export S3_BUCKET=umbrella
export S3_ENDPOINT_URL=http://localhost:9000
export AWS_ACCESS_KEY_ID=minioadmin
export AWS_SECRET_ACCESS_KEY=minioadmin

python -m umbrella_email processor
```

## Docker

### Build
```bash
# From repository root
docker build -t umbrella-email:latest -f connectors/email/Dockerfile .
```

### Run Stage 1 (Connector)
```bash
docker run --rm \
  -e CONNECTOR_NAME=email-connector \
  -e IMAP_HOST=imap.gmail.com \
  -e IMAP_USER=user@example.com \
  -e IMAP_PASSWORD=secret \
  -e KAFKA_BOOTSTRAP_SERVERS=kafka:9092 \
  -e S3_BUCKET=umbrella \
  -e S3_ENDPOINT_URL=http://minio:9000 \
  -e AWS_ACCESS_KEY_ID=minioadmin \
  -e AWS_SECRET_ACCESS_KEY=minioadmin \
  umbrella-email:latest \
  python -m umbrella_email connector
```

### Run Stage 2 (Processor)
```bash
docker run --rm \
  -e PROCESSOR_KAFKA_BOOTSTRAP_SERVERS=kafka:9092 \
  -e PROCESSOR_SOURCE_TOPIC=raw-messages \
  -e PROCESSOR_OUTPUT_TOPIC=parsed-messages \
  -e S3_BUCKET=umbrella \
  -e S3_ENDPOINT_URL=http://minio:9000 \
  -e AWS_ACCESS_KEY_ID=minioadmin \
  -e AWS_SECRET_ACCESS_KEY=minioadmin \
  umbrella-email:latest \
  python -m umbrella_email processor
```

## Kubernetes

See `deploy/k8s/umbrella-connectors/email-processor-deployment.yaml`

## Testing

```bash
pytest tests/ -v
```

## Dependencies

- `umbrella-connector-framework` - Base connector infrastructure
- `boto3` - S3 access for claim-check pattern
- `email` (stdlib) - MIME parsing
- `aioimaplib` - Async IMAP client (Stage 1 only)
