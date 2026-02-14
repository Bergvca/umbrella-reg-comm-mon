# Elasticsearch + Logstash Setup Plan

## Goal

Deploy a single-node Elasticsearch cluster and Logstash instance that consumes from Kafka topics and indexes data into ES. Runs in Docker containers deployable to the `umbrella-storage` K8s namespace. Designed for single-node MVP but scalable to a multi-node cluster.

---

## 1. Data Flow

```
Kafka                          Logstash                      Elasticsearch
─────                          ────────                      ─────────────

normalized-messages ──┐
                      ├──→ logstash pipeline ──→ messages-YYYY.MM index
processing-results ───┘     (merge/upsert)

alerts ────────────────────→ logstash pipeline ──→ alerts-YYYY.MM index
```

### Kafka Topics → ES Indices

| Kafka Topic | Logstash Pipeline | ES Index Pattern | Document ID | Purpose |
|---|---|---|---|---|
| `normalized-messages` | `messages` | `messages-YYYY.MM` | `message_id` | Normalized comms — baseline document |
| `processing-results` | `messages` | `messages-YYYY.MM` | `message_id` | Enrichments (NLP, transcription, translation) — upserted onto same doc |
| `alerts` | `alerts` | `alerts-YYYY.MM` | auto-generated | Compliance alerts with scores and matched policies |

The `messages` pipeline consumes from **both** `normalized-messages` and `processing-results`. Documents are keyed by `message_id` so enrichments upsert onto the original normalized message. This gives the UI a single document per communication with all enrichments merged in.

The `alerts` pipeline is separate — alerts are their own documents with a reference back to the source `message_id`.

### Index Lifecycle

Monthly rollover (`messages-YYYY.MM`, `alerts-YYYY.MM`) via index templates. ILM policy handles:
- **Hot** → **Warm** (after 30 days, force merge to 1 segment)
- **Cold** (after 90 days, reduce replicas to 0 for MVP)
- **Delete** (after 2555 days / 7 years — FINRA/MiFID II retention)

---

## 2. ES Index Mappings

### `messages-*` — Normalized + Enriched Communications

Derived from `NormalizedMessage` schema plus processing enrichment fields:

```json
{
  "mappings": {
    "properties": {
      "message_id":    { "type": "keyword" },
      "channel":       { "type": "keyword" },
      "direction":     { "type": "keyword" },
      "timestamp":     { "type": "date" },
      "participants": {
        "type": "nested",
        "properties": {
          "id":   { "type": "keyword" },
          "name": { "type": "text", "fields": { "keyword": { "type": "keyword" } } },
          "role": { "type": "keyword" }
        }
      },
      "body_text":     { "type": "text", "analyzer": "standard" },
      "audio_ref":     { "type": "keyword" },
      "attachments": {
        "type": "nested",
        "properties": {
          "name":         { "type": "text", "fields": { "keyword": { "type": "keyword" } } },
          "content_type": { "type": "keyword" },
          "s3_uri":       { "type": "keyword" }
        }
      },
      "metadata":      { "type": "object", "enabled": true },

      "transcript":    { "type": "text", "analyzer": "standard" },
      "language":      { "type": "keyword" },
      "translated_text": { "type": "text", "analyzer": "standard" },
      "entities":      { "type": "nested",
        "properties": {
          "text":  { "type": "text", "fields": { "keyword": { "type": "keyword" } } },
          "label": { "type": "keyword" },
          "start": { "type": "integer" },
          "end":   { "type": "integer" }
        }
      },
      "sentiment":     { "type": "keyword" },
      "sentiment_score": { "type": "float" },
      "risk_score":    { "type": "float" },
      "matched_policies": { "type": "keyword" },
      "processing_status": { "type": "keyword" }
    }
  }
}
```

Key design choices:
- `participants` and `attachments` are `nested` so queries can match on field combinations (e.g. participant name + role)
- `body_text`, `transcript`, `translated_text` are `text` for full-text search
- `metadata` is a dynamic `object` — stores channel-specific fields (subject, body_html, raw_eml_s3_uri)
- Enrichment fields (`transcript`, `entities`, `sentiment`, etc.) start null and are filled by upsert from `processing-results`

### `alerts-*` — Compliance Alerts

```json
{
  "mappings": {
    "properties": {
      "alert_id":      { "type": "keyword" },
      "message_id":    { "type": "keyword" },
      "channel":       { "type": "keyword" },
      "timestamp":     { "type": "date" },
      "alert_type":    { "type": "keyword" },
      "severity":      { "type": "keyword" },
      "risk_score":    { "type": "float" },
      "matched_policies": { "type": "keyword" },
      "matched_terms": { "type": "keyword" },
      "excerpt":       { "type": "text" },
      "participants": {
        "type": "nested",
        "properties": {
          "id":   { "type": "keyword" },
          "name": { "type": "text", "fields": { "keyword": { "type": "keyword" } } },
          "role": { "type": "keyword" }
        }
      },
      "review_status": { "type": "keyword" },
      "reviewer":      { "type": "keyword" },
      "reviewed_at":   { "type": "date" },
      "disposition":   { "type": "keyword" },
      "notes":         { "type": "text" }
    }
  }
}
```

---

## 3. Logstash Pipelines

### Pipeline: `messages`

Consumes from `normalized-messages` and `processing-results`, upserts into `messages-*`.

```
input {
  kafka {
    bootstrap_servers => "kafka:9092"
    topics => ["normalized-messages", "processing-results"]
    group_id => "logstash-messages"
    codec => "json"
    decorate_events => "basic"
    auto_offset_reset => "earliest"
  }
}

filter {
  # Parse timestamp for index routing
  date {
    match => ["timestamp", "ISO8601"]
    target => "@timestamp"
  }

  # Build monthly index suffix from message timestamp
  ruby {
    code => '
      t = event.get("@timestamp")&.time
      if t
        event.set("[@metadata][index_suffix]", t.strftime("%Y.%m"))
      else
        event.set("[@metadata][index_suffix]", Time.now.utc.strftime("%Y.%m"))
      end
    '
  }

  # Ensure message_id exists for document ID
  if ![message_id] {
    drop {}
  }
}

output {
  elasticsearch {
    hosts => ["http://elasticsearch:9200"]
    index => "messages-%{[@metadata][index_suffix]}"
    document_id => "%{message_id}"
    action => "update"
    doc_as_upsert => true
    retry_on_conflict => 3
  }
}
```

Key behaviour:
- `action => "update"` with `doc_as_upsert => true` — first message from `normalized-messages` creates the doc, subsequent messages from `processing-results` merge enrichment fields in
- `retry_on_conflict => 3` — handles race conditions when multiple processing services enrich the same message concurrently
- `document_id => "%{message_id}"` — deduplication and upsert key

### Pipeline: `alerts`

```
input {
  kafka {
    bootstrap_servers => "kafka:9092"
    topics => ["alerts"]
    group_id => "logstash-alerts"
    codec => "json"
    auto_offset_reset => "earliest"
  }
}

filter {
  date {
    match => ["timestamp", "ISO8601"]
    target => "@timestamp"
  }

  ruby {
    code => '
      t = event.get("@timestamp")&.time
      if t
        event.set("[@metadata][index_suffix]", t.strftime("%Y.%m"))
      else
        event.set("[@metadata][index_suffix]", Time.now.utc.strftime("%Y.%m"))
      end
    '
  }

  # Set default review status
  if ![review_status] {
    mutate {
      add_field => { "review_status" => "pending" }
    }
  }
}

output {
  elasticsearch {
    hosts => ["http://elasticsearch:9200"]
    index => "alerts-%{[@metadata][index_suffix]}"
    document_id => "%{[alert_id]}"
  }
}
```

### Pipeline Configuration (`pipelines.yml`)

```yaml
- pipeline.id: messages
  path.config: "/usr/share/logstash/pipeline/messages.conf"
  pipeline.workers: 2
  pipeline.batch.size: 500

- pipeline.id: alerts
  path.config: "/usr/share/logstash/pipeline/alerts.conf"
  pipeline.workers: 1
  pipeline.batch.size: 250
```

---

## 4. Docker Images

### Elasticsearch

**Image**: `docker.elastic.co/elasticsearch/elasticsearch:9.3.0`

Single-node mode with security disabled for MVP (xpack.security.enabled=false). Scale by adding nodes and changing `discovery.type` from `single-node` to `multi-node` with seed hosts.

### Logstash

**Image**: `docker.elastic.co/logstash/logstash:9.3.0`

Uses the kafka input plugin (bundled) and elasticsearch output plugin (bundled). No additional plugin installs needed.

Version pinned to match ES — major version must always match.

---

## 5. File Structure

```
infrastructure/elasticsearch/
  Dockerfile                        # Thin ES wrapper (copies index templates)
  docker-compose.yml                # Local dev: ES + Logstash + Kafka network
  config/
    elasticsearch.yml               # ES node config
    index-templates/
      messages-template.json        # Index template for messages-*
      alerts-template.json          # Index template for alerts-*
      ilm-policy.json               # ILM retention policy
    init-templates.sh               # Script to load templates into ES on startup

infrastructure/logstash/
  Dockerfile                        # Thin wrapper (copies pipeline configs)
  config/
    logstash.yml                    # Logstash settings (monitoring, pipeline config path)
    pipelines.yml                   # Multi-pipeline config
  pipeline/
    messages.conf                   # Kafka → ES messages pipeline
    alerts.conf                     # Kafka → ES alerts pipeline

deploy/k8s/umbrella-storage/
  namespace.yaml                    # umbrella-storage namespace
  elasticsearch/
    statefulset.yaml                # Single-node ES StatefulSet
    service.yaml                    # ClusterIP service (port 9200)
    configmap.yaml                  # elasticsearch.yml + index templates
    job-init-templates.yaml         # One-shot Job to load index templates + ILM
  logstash/
    deployment.yaml                 # Logstash Deployment (stateless)
    configmap.yaml                  # pipelines.yml + pipeline configs
    service.yaml                    # ClusterIP for Logstash monitoring API (9600)
```

---

## 6. Local Development (docker-compose)

Extends the existing Kafka docker-compose via Docker network:

```
infrastructure/elasticsearch/docker-compose.yml
```

Joins the Kafka network so Logstash can reach `kafka:9092`. Alternatively, uses the Kafka external listener at `host.docker.internal:19092`.

Components:
- **elasticsearch**: single-node, ports 9200 (API) + 9300 (transport)
- **logstash**: both pipelines, connected to ES + Kafka
- **es-init**: one-shot container that waits for ES to be healthy, then loads index templates and ILM policy

---

## 7. Elasticsearch Configuration

### `elasticsearch.yml`

```yaml
cluster.name: umbrella
node.name: es-node-0
discovery.type: single-node

network.host: 0.0.0.0
http.port: 9200

xpack.security.enabled: false

path.data: /usr/share/elasticsearch/data
path.logs: /usr/share/elasticsearch/logs
```

For production scale-out, change:
- `discovery.type` → remove (defaults to multi-node)
- Add `discovery.seed_hosts` and `cluster.initial_master_nodes`
- Enable `xpack.security.enabled: true` with TLS

### Resource Sizing (MVP)

| Setting | Value |
|---|---|
| JVM heap | 512m (`ES_JAVA_OPTS=-Xms512m -Xmx512m`) |
| Disk | 10Gi PVC |
| CPU | 250m request / 1 limit |
| Memory | 1Gi request / 2Gi limit |

---

## 8. Logstash Configuration

### `logstash.yml`

```yaml
http.host: "0.0.0.0"
http.port: 9600
log.level: info
pipeline.ordered: auto
config.reload.automatic: true
config.reload.interval: 30s
xpack.monitoring.enabled: false
```

### Resource Sizing (MVP)

| Setting | Value |
|---|---|
| JVM heap | 512m (`LS_JAVA_OPTS=-Xms512m -Xmx512m`) |
| CPU | 250m request / 1 limit |
| Memory | 1Gi request / 2Gi limit |

---

## 9. K8s Deployment Details

### Elasticsearch StatefulSet

```
replicas: 1
serviceName: elasticsearch-headless

containers:
  - name: elasticsearch
    image: docker.elastic.co/elasticsearch/elasticsearch:9.3.0
    ports: [9200, 9300]
    env:
      discovery.type: single-node
      cluster.name: umbrella
      xpack.security.enabled: "false"
      ES_JAVA_OPTS: "-Xms512m -Xmx512m"
    volumeMounts:
      - name: data → /usr/share/elasticsearch/data
    resources:
      requests: { cpu: 250m, memory: 1Gi }
      limits:   { cpu: 1, memory: 2Gi }
    readinessProbe:
      httpGet: { path: /_cluster/health?local=true, port: 9200 }
      initialDelaySeconds: 30
    livenessProbe:
      httpGet: { path: /_cluster/health?local=true, port: 9200 }
      initialDelaySeconds: 60

volumeClaimTemplates:
  - name: data
    storage: 10Gi
```

### Logstash Deployment

Stateless — no PVC needed. Reads pipeline config from ConfigMap.

```
replicas: 1

containers:
  - name: logstash
    image: docker.elastic.co/logstash/logstash:9.3.0
    ports: [9600]
    env:
      LS_JAVA_OPTS: "-Xms512m -Xmx512m"
      ELASTICSEARCH_HOSTS: "http://elasticsearch.umbrella-storage.svc:9200"
      KAFKA_BOOTSTRAP_SERVERS: "kafka.umbrella-streaming.svc:9092"
    volumeMounts:
      - name: pipeline → /usr/share/logstash/pipeline/
      - name: config → /usr/share/logstash/config/
    resources:
      requests: { cpu: 250m, memory: 1Gi }
      limits:   { cpu: 1, memory: 2Gi }
    readinessProbe:
      httpGet: { path: /, port: 9600 }
      initialDelaySeconds: 60
    livenessProbe:
      httpGet: { path: /, port: 9600 }
      initialDelaySeconds: 90
```

### Service DNS

| Service | Address |
|---|---|
| Elasticsearch | `elasticsearch.umbrella-storage.svc:9200` |
| Logstash monitoring | `logstash.umbrella-storage.svc:9600` |
| Kafka (cross-namespace) | `kafka.umbrella-streaming.svc:9092` |

---

## 10. Index Template Loading

A one-shot init Job (or docker-compose init container) loads:

1. **ILM policy** — `PUT _ilm/policy/umbrella-retention`
2. **Messages index template** — `PUT _index_template/messages-template` (applies to `messages-*`)
3. **Alerts index template** — `PUT _index_template/alerts-template` (applies to `alerts-*`)

The init script waits for ES to be green/yellow, then uses `curl` to PUT each template. Idempotent — safe to re-run.

---

## 11. Implementation Order

1. **ES config + index templates** — `infrastructure/elasticsearch/config/`
2. **Logstash pipeline configs** — `infrastructure/logstash/pipeline/` + `config/`
3. **ES Dockerfile** — thin wrapper copying config
4. **Logstash Dockerfile** — thin wrapper copying pipelines
5. **`docker-compose.yml`** — local dev ES + Logstash connected to Kafka
6. **Verify locally** — `docker compose up`, send test JSON to `normalized-messages` via kafka-console-producer, confirm it appears in ES
7. **K8s namespace + ES manifests** — StatefulSet, Service, ConfigMap, init Job
8. **K8s Logstash manifests** — Deployment, ConfigMap, Service
9. **End-to-end test** — produce to `normalized-messages` and `alerts` on Kafka, verify documents indexed in ES

---

## 12. Validation Checklist

- [ ] `docker compose up` starts ES (single-node) + Logstash, both healthy
- [ ] Index templates loaded: `GET _index_template/messages-template` and `alerts-template` return 200
- [ ] ILM policy loaded: `GET _ilm/policy/umbrella-retention` returns 200
- [ ] Produce a NormalizedMessage JSON to `normalized-messages` → appears in `messages-YYYY.MM` index within seconds
- [ ] Produce a processing-results JSON with same `message_id` → document in ES is updated (upsert) with enrichment fields
- [ ] Produce an alert JSON to `alerts` → appears in `alerts-YYYY.MM` index
- [ ] `GET messages-*/_search?q=*` returns indexed documents with correct field types
- [ ] Logstash consumer groups (`logstash-messages`, `logstash-alerts`) visible in Kafka with zero lag after processing
- [ ] K8s YAML files parse without errors
