# Elasticsearch + Logstash Quick Start

## Local Development (Docker Compose)

### Prerequisites
- Docker and Docker Compose installed
- Kafka running: `cd infrastructure/kafka && docker compose up -d`

### Start ES + Logstash
```bash
cd infrastructure/elasticsearch
docker compose up -d
```

### Verify Setup
```bash
# Cluster health
curl http://localhost:9200/_cluster/health

# Templates loaded
curl http://localhost:9200/_index_template

# Logstash running
curl http://localhost:9600/api/pipelines
```

### Test Message Indexing
```bash
# Produce a message to Kafka
kafka-console-producer --bootstrap-server localhost:19092 --topic normalized-messages << 'EOF'
{
  "message_id": "test-001",
  "channel": "email",
  "direction": "inbound",
  "timestamp": "2026-02-12T10:00:00Z",
  "participants": [{"id": "alice", "name": "Alice", "role": "trader"}],
  "body_text": "Test message"
}
EOF

# Query Elasticsearch
curl http://localhost:9200/messages-2026.02/_search?pretty

# Cleanup
docker compose down
```

## Kubernetes Deployment

### Prerequisites
- K8s cluster with `umbrella-streaming` namespace containing Kafka
- `kubectl` configured

### Deploy
```bash
# Create namespace and ES resources
kubectl apply -f deploy/k8s/umbrella-storage/namespace.yaml
kubectl apply -f deploy/k8s/umbrella-storage/elasticsearch/

# Deploy Logstash
kubectl apply -f deploy/k8s/umbrella-storage/logstash/

# Wait for ready
kubectl rollout status statefulset/elasticsearch -n umbrella-storage
kubectl rollout status deployment/logstash -n umbrella-storage
```

### Access
```bash
# Port-forward ES API
kubectl port-forward -n umbrella-storage svc/elasticsearch 9200:9200

# Port-forward Logstash
kubectl port-forward -n umbrella-storage svc/logstash 9600:9600

# Check logs
kubectl logs -n umbrella-storage -f deployment/logstash
kubectl logs -n umbrella-storage -f statefulset.apps/elasticsearch
```

## Data Flow

**Messages Pipeline** (`normalized-messages` + `processing-results` → `messages-YYYY.MM`)
- Consumes from two Kafka topics
- Upserts documents by `message_id`
- Enrichments merge into source document

**Alerts Pipeline** (`alerts` → `alerts-YYYY.MM`)
- Separate topic for compliance alerts
- Each alert is its own document with reference to source `message_id`

## Index Patterns

- **Messages**: `messages-YYYY.MM` (monthly rollover)
- **Alerts**: `alerts-YYYY.MM` (monthly rollover)
- **ILM Policy**: umbrella-retention (hot/warm/cold/delete, 7-year retention)

## Useful Queries

```bash
# List all indices
curl http://localhost:9200/_cat/indices?v

# Search messages
curl http://localhost:9200/messages-*/_search?q=body_text:*

# Search alerts by severity
curl -X POST http://localhost:9200/alerts-*/_search -H 'Content-Type: application/json' -d '{
  "query": { "term": { "severity": "high" } }
}'

# Check consumer lag
kafka-consumer-groups --bootstrap-server kafka:9092 --group logstash-messages --describe
```

## Troubleshooting

### No documents indexing
1. Check Kafka topics exist: `kafka-topics.sh --bootstrap-server kafka:9092 --list`
2. Check consumer lag: `kafka-consumer-groups --bootstrap-server kafka:9092 --group logstash-messages --describe`
3. Check Logstash logs: `docker logs umbrella-logstash` or `kubectl logs -l app=logstash -n umbrella-storage`

### ES not responding
1. Check health: `curl http://localhost:9200/_cluster/health`
2. Check logs: `docker logs umbrella-elasticsearch`
3. Check storage: `docker volume ls | grep elasticsearch`

### Templates not loading
1. Check if loaded: `curl http://localhost:9200/_index_template/messages-template`
2. Check init container: `docker logs umbrella-es-init`
3. Manually load: `curl -X PUT http://localhost:9200/_index_template/messages-template @messages-template.json`

## Documentation

- Full setup guide: [`infrastructure/elasticsearch/README.md`](../infrastructure/elasticsearch/README.md)
- Implementation details: [`ELASTICSEARCH_IMPLEMENTATION_SUMMARY.md`](ELASTICSEARCH_IMPLEMENTATION_SUMMARY.md)
- Original plan: [`elasticsearch_setup.md`](elasticsearch_setup.md)

## Key Contacts

- ES cluster: `umbrella-storage` namespace, `elasticsearch.umbrella-storage.svc:9200`
- Logstash: `umbrella-storage` namespace, `logstash.umbrella-storage.svc`
- Kafka: `umbrella-streaming` namespace, `kafka.umbrella-streaming.svc:9092`
