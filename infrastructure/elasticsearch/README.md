# Elasticsearch + Logstash Setup

This directory contains the configuration and deployment files for a single-node Elasticsearch cluster with Logstash pipelines that consume from Kafka topics and index data into Elasticsearch.

## Architecture

- **Elasticsearch 9.3.0**: Single-node cluster (scalable to multi-node by updating K8s manifests)
- **Logstash 9.3.0**: Two pipelines for processing Kafka events
  - `messages`: Merges normalized messages with processing enrichments
  - `alerts`: Indexes compliance alerts
- **Data Flow**: Kafka → Logstash → Elasticsearch
- **Index Lifecycle**: Monthly rollover with ILM policy (hot/warm/cold/delete phases, 7-year retention)

## Local Development

### Prerequisites

1. Kafka running on Docker (from `infrastructure/kafka/`)
2. Docker and Docker Compose installed

### Starting the Stack

```bash
cd infrastructure/elasticsearch
docker compose up -d
```

This starts:
- Elasticsearch on `http://localhost:9200`
- Logstash (monitoring API on `http://localhost:9600`)
- ES init container (loads templates and ILM policy)

### Verification

```bash
# Check cluster health
curl http://localhost:9200/_cluster/health

# List index templates
curl http://localhost:9200/_index_template

# List indices
curl http://localhost:9200/_cat/indices

# Logstash pipelines status
curl http://localhost:9600/api/pipelines
```

### Testing Data Flow

1. **Produce a normalized message**:
```bash
kafka-console-producer --bootstrap-server localhost:19092 \
  --topic normalized-messages << EOF
{
  "message_id": "msg-001",
  "channel": "email",
  "direction": "inbound",
  "timestamp": "2026-02-12T10:00:00Z",
  "participants": [{"id": "user1", "name": "Alice", "role": "trader"}],
  "body_text": "Market update"
}
EOF
```

2. **Query the indexed document**:
```bash
curl http://localhost:9200/messages-2026.02/_search?pretty
```

3. **Produce an enrichment (processing-results)**:
```bash
kafka-console-producer --bootstrap-server localhost:19092 \
  --topic processing-results << EOF
{
  "message_id": "msg-001",
  "transcript": "market update transcript",
  "sentiment": "neutral",
  "sentiment_score": 0.5
}
EOF
```

4. **Verify upsert** - the document in ES should now contain enrichment fields

5. **Produce an alert**:
```bash
kafka-console-producer --bootstrap-server localhost:19092 \
  --topic alerts << EOF
{
  "alert_id": "alert-001",
  "message_id": "msg-001",
  "channel": "email",
  "timestamp": "2026-02-12T10:01:00Z",
  "alert_type": "compliance",
  "severity": "high",
  "risk_score": 0.85,
  "matched_policies": ["prohibited-terms"],
  "matched_terms": ["sensitive-phrase"]
}
EOF
```

6. **Query alerts**:
```bash
curl http://localhost:9200/alerts-2026.02/_search?pretty
```

## Kubernetes Deployment

### Prerequisites

1. Kubernetes cluster with `umbrella-streaming` namespace for Kafka
2. Kafka accessible at `kafka.umbrella-streaming.svc:9092`
3. `kubectl` configured

### Deploy to K8s

```bash
# Create namespace and deploy Elasticsearch
kubectl apply -f deploy/k8s/umbrella-storage/namespace.yaml
kubectl apply -f deploy/k8s/umbrella-storage/elasticsearch/

# Deploy Logstash
kubectl apply -f deploy/k8s/umbrella-storage/logstash/

# Check status
kubectl get pods -n umbrella-storage
kubectl logs -n umbrella-storage -l app=elasticsearch
kubectl logs -n umbrella-storage -l app=logstash
```

### Access in K8s

- **Elasticsearch API**: `kubectl port-forward -n umbrella-storage svc/elasticsearch 9200:9200`
- **Logstash monitoring**: `kubectl port-forward -n umbrella-storage svc/logstash 9600:9600`

### Verify Templates Loaded

```bash
# Port-forward ES API
kubectl port-forward -n umbrella-storage svc/elasticsearch 9200:9200 &

# Check templates
curl http://localhost:9200/_index_template/messages-template
curl http://localhost:9200/_index_template/alerts-template
curl http://localhost:9200/_ilm/policy/umbrella-retention
```

## Configuration Files

### Elasticsearch

- **`config/elasticsearch.yml`**: Node configuration
- **`config/index-templates/messages-template.json`**: Mapping for normalized + enriched messages
- **`config/index-templates/alerts-template.json`**: Mapping for compliance alerts
- **`config/index-templates/ilm-policy.json`**: Index lifecycle policy (hot/warm/cold/delete)
- **`config/init-templates.sh`**: Script to load templates into ES

### Logstash

- **`config/logstash.yml`**: Logstash settings
- **`config/pipelines.yml`**: Multi-pipeline configuration
- **`pipeline/messages.conf`**: Kafka → ES messages pipeline (upsert on message_id)
- **`pipeline/alerts.conf`**: Kafka → ES alerts pipeline

## Index Mappings

### `messages-YYYY.MM`

Stores normalized communications + enrichments:
- `message_id` (keyword): Unique identifier, used as document ID
- `channel` (keyword): Communication channel (email, chat, call, etc.)
- `direction` (keyword): inbound/outbound
- `timestamp` (date): Message timestamp
- `participants` (nested): Array of {id, name, role}
- `body_text` (text): Message content
- `audio_ref` (keyword): S3 reference to audio recording
- `attachments` (nested): Array of {name, content_type, s3_uri}
- `metadata` (object): Dynamic channel-specific fields
- **Enrichment fields**:
  - `transcript` (text): Speech-to-text result
  - `language` (keyword): Detected language
  - `translated_text` (text): Translation
  - `entities` (nested): NER results {text, label, start, end}
  - `sentiment` (keyword): positive/neutral/negative
  - `sentiment_score` (float): -1.0 to 1.0
  - `risk_score` (float): 0.0 to 1.0
  - `matched_policies` (keyword): Policy violations
  - `processing_status` (keyword): pending/completed/failed

### `alerts-YYYY.MM`

Stores compliance alerts:
- `alert_id` (keyword): Unique identifier, used as document ID
- `message_id` (keyword): Reference to source message
- `channel` (keyword): Source communication channel
- `timestamp` (date): Alert creation time
- `alert_type` (keyword): compliance/risk/other
- `severity` (keyword): critical/high/medium/low
- `risk_score` (float): Alert severity score
- `matched_policies` (keyword): Triggered policies
- `matched_terms` (keyword): Flagged terms/patterns
- `excerpt` (text): Text snippet from message
- `participants` (nested): People involved in communication
- `review_status` (keyword): pending/reviewed/dismissed
- `reviewer` (keyword): User who reviewed
- `reviewed_at` (date): Review timestamp
- `disposition` (keyword): approval/denial/escalation
- `notes` (text): Review notes

## Data Flow Details

### Messages Pipeline

1. **Input**: Consumes from `normalized-messages` and `processing-results` topics
2. **Filter**:
   - Parses ISO8601 timestamp
   - Generates monthly index suffix (YYYY.MM)
   - Drops documents missing `message_id`
3. **Output**:
   - Upserts to `messages-YYYY.MM` index
   - Uses `message_id` as document ID
   - Updates action with `doc_as_upsert=true`
   - Retries up to 3 times on conflict

**Result**: First event from `normalized-messages` creates the document, subsequent events from `processing-results` merge enrichment fields into the same document.

### Alerts Pipeline

1. **Input**: Consumes from `alerts` topic
2. **Filter**:
   - Parses timestamp
   - Generates monthly index suffix
   - Sets default `review_status: "pending"` if missing
3. **Output**: Indexes to `alerts-YYYY.MM` with `alert_id` as document ID

## Index Lifecycle (ILM)

Monthly indices with automatic phase transitions:

| Phase | Age | Actions |
|-------|-----|---------|
| **Hot** | 0-30d | Real-time ingestion |
| **Warm** | 30-90d | Force merge to 1 segment, priority=50 |
| **Cold** | 90-2555d | Priority=0, searchable snapshot |
| **Delete** | 2555d+ (7 years) | Delete indices |

Complies with FINRA and MiFID II regulations (7-year retention).

## Resource Sizing (MVP)

| Component | Request | Limit |
|-----------|---------|-------|
| **Elasticsearch** | CPU: 250m, Memory: 1Gi | CPU: 1000m, Memory: 2Gi |
| **Logstash** | CPU: 250m, Memory: 1Gi | CPU: 1000m, Memory: 2Gi |
| **JVM Heap** | 512m | 512m |
| **Storage** | 10Gi PVC | - |

## Scaling Considerations

### Single-Node → Multi-Node

To scale Elasticsearch to multiple nodes:

1. Change `discovery.type` from `single-node` to multi-node in `elasticsearch.yml`
2. Add `discovery.seed_hosts` and `cluster.initial_master_nodes` configuration
3. Update K8s StatefulSet replicas from 1 to N
4. Update templates: increase `number_of_replicas` from 0 to 1+ (for redundancy)
5. Enable security: set `xpack.security.enabled: true` and configure TLS

### Logstash Scaling

1. Update K8s Deployment replicas for horizontal scaling
2. Logstash consumer groups handle partition assignment automatically
3. Increase `pipeline.workers` and `pipeline.batch.size` for higher throughput

## Troubleshooting

### Elasticsearch not healthy

```bash
# Check logs
kubectl logs -n umbrella-storage elasticsearch-0

# Check persistence
kubectl get pvc -n umbrella-storage

# Verify connectivity to ES
kubectl run -it --rm debug --image=curlimages/curl --restart=Never -n umbrella-storage -- \
  curl http://elasticsearch:9200/_cluster/health
```

### Logstash not processing

```bash
# Check logs
kubectl logs -n umbrella-storage -l app=logstash

# Check pipeline status
kubectl port-forward -n umbrella-storage svc/logstash 9600:9600
curl http://localhost:9600/api/pipelines
```

### No documents in ES

```bash
# Verify topics exist and have data
kafka-console-consumer --bootstrap-server kafka:9092 --topic normalized-messages --from-beginning

# Check Logstash consumer group lag
kafka-consumer-groups --bootstrap-server kafka:9092 --group logstash-messages --describe
```

## Related Documentation

- [Elasticsearch Setup Plan](../../docs/elasticsearch_setup.md)
- [Kafka Configuration](../kafka/README.md)
- [K8s Deployment Guide](../../deploy/k8s/README.md)
