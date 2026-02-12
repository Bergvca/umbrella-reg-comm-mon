# Kafka Message Bus Setup Plan

## Goal

Deploy Apache Kafka in KRaft mode (no ZooKeeper) as a Docker container running in the `umbrella-streaming` Kubernetes namespace. This provides the central message bus that all Umbrella services produce to and consume from.

---

## 1. Topic Inventory

Derived from the existing codebase:

| Topic | Partitions | Replication | Producer(s) | Consumer(s) | Key |
|---|---|---|---|---|---|
| `raw-messages` | 1 | 1 | Connectors (via `KafkaProducerWrapper`) | EmailProcessor | `raw_message_id` |
| `parsed-messages` | 1 | 1 | EmailProcessor | IngestionService | `raw_message_id` |
| `normalized-messages` | 1 | 1 | IngestionService | Processing services (NLP, transcription, translation) | `message_id` |
| `processing-results` | 1 | 1 | Processing services | Elasticsearch indexer | `message_id` |
| `alerts` | 1 | 1 | NLP service | Elasticsearch indexer, UI backend | `message_id` |
| `dead-letter` | 1 | 1 | Connector framework (`DeadLetterHandler`) | Ops / manual reprocessing | `raw_message_id` |
| `normalized-messages-dlq` | 1 | 1 | IngestionService (future) | Ops / manual reprocessing | `message_id` |

**MVP rationale**: Single partition and replication factor 1 for simplicity — single-broker deployment. Scale up partitions and replication when moving to production (3-broker cluster).

---

## 2. Docker Image

Use the official Apache Kafka image which supports KRaft natively, no ZooKeeper required.

**Image**: `apache/kafka:4.1.1` (latest stable, KRaft-only — ZooKeeper removed in 4.0)

### Dockerfile (`infrastructure/kafka/Dockerfile`)

Thin wrapper over the official image that:
1. Copies in a topic-init entrypoint script
2. Copies a `create-topics.sh` script to auto-create all platform topics on first boot

The Kafka configuration itself is driven entirely by environment variables at deploy time (K8s manifests / Helm values), not baked into the image.

### `create-topics.sh` (`infrastructure/kafka/scripts/create-topics.sh`)

Idempotent script that runs `kafka-topics.sh --create --if-not-exists` for each topic from the inventory above. Called by an init container or a post-start K8s Job.

### `docker-compose.yml` (`infrastructure/kafka/docker-compose.yml`)

For local development — runs a single-broker KRaft cluster with all topics pre-created. Services (connectors, processors, ingestion) can connect via `localhost:9092`. This mirrors the `bootstrap_servers` default across all config classes.

---

## 3. Kubernetes Deployment

**Namespace**: `umbrella-streaming` (directory already scaffolded at `deploy/k8s/umbrella-streaming/`)

### Architecture: StatefulSet (1 broker)

Single-broker MVP. StatefulSet is used for stable network identity and persistent storage, making it straightforward to scale to 3 replicas for production.

### K8s Manifests

| File | Resource | Purpose |
|---|---|---|
| `namespace.yaml` | Namespace | `umbrella-streaming` |
| `statefulset.yaml` | StatefulSet | 1 Kafka broker replica in KRaft combined mode (scale to 3 for prod) |
| `service-headless.yaml` | Headless Service | Stable DNS for broker identity (`kafka-0.kafka-headless`) |
| `service.yaml` | ClusterIP Service | Client-facing bootstrap endpoint (`kafka.umbrella-streaming.svc:9092`) |
| `configmap.yaml` | ConfigMap | Shared Kafka server properties (log dirs, retention, KRaft settings) |
| `pvc.yaml` | PVC template | Persistent volume for each broker's log directory |
| `job-create-topics.yaml` | Job | One-shot topic creation after cluster is ready |
| `networkpolicy.yaml` | NetworkPolicy | Restrict access to Kafka to only Umbrella namespaces |
| `podmonitor.yaml` | PodMonitor | Prometheus scraping of JMX metrics |

### StatefulSet Details

```
replicas: 1
podManagementPolicy: Parallel

containers:
  - name: kafka
    image: apache/kafka:4.1.1
    ports:
      - 9092  (client)
      - 9093  (controller)
    env:
      KAFKA_NODE_ID:                  0
      KAFKA_PROCESS_ROLES:            broker,controller
      KAFKA_CONTROLLER_QUORUM_VOTERS: 0@kafka-0.kafka-headless:9093
      KAFKA_LISTENERS:                PLAINTEXT://:9092,CONTROLLER://:9093
      KAFKA_INTER_BROKER_LISTENER_NAME: PLAINTEXT
      KAFKA_CONTROLLER_LISTENER_NAMES:  CONTROLLER
      KAFKA_ADVERTISED_LISTENERS:     PLAINTEXT://kafka-0.kafka-headless.umbrella-streaming.svc:9092
      KAFKA_LOG_DIRS:                 /var/kafka-logs
      KAFKA_NUM_PARTITIONS:           1
      KAFKA_DEFAULT_REPLICATION_FACTOR: 1
      KAFKA_MIN_INSYNC_REPLICAS:      1
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
      KAFKA_LOG_RETENTION_HOURS:      168  (7 days)
      KAFKA_LOG_RETENTION_BYTES:      -1   (unlimited, time-based only)
      KAFKA_COMPRESSION_TYPE:         producer  (honour producer's gzip)
      CLUSTER_ID:                     from ConfigMap (generated once via kafka-storage random-uuid)

    volumeMounts:
      - name: data
        mountPath: /var/kafka-logs

    resources:
      requests: { cpu: 250m, memory: 512Mi }
      limits:   { cpu: 1, memory: 2Gi }

    readinessProbe:
      tcpSocket: { port: 9092 }
      initialDelaySeconds: 30
    livenessProbe:
      tcpSocket: { port: 9092 }
      initialDelaySeconds: 60

volumeClaimTemplates:
  - metadata: { name: data }
    spec:
      accessModes: [ReadWriteOnce]
      resources:
        requests: { storage: 10Gi }
```

### Topic Creation Job

Runs after the StatefulSet is ready. Uses the same Kafka image to execute `create-topics.sh` against the bootstrap service.

```
apiVersion: batch/v1
kind: Job
metadata:
  name: kafka-create-topics
spec:
  template:
    spec:
      containers:
        - name: create-topics
          image: apache/kafka:4.1.1
          command: ["/bin/bash", "/scripts/create-topics.sh"]
          env:
            - name: KAFKA_BOOTSTRAP
              value: kafka.umbrella-streaming.svc:9092
          volumeMounts:
            - name: scripts
              mountPath: /scripts
      volumes:
        - name: scripts
          configMap:
            name: kafka-topic-scripts
      restartPolicy: OnFailure
```

### Service DNS

All services across the cluster connect to Kafka via:
```
kafka.umbrella-streaming.svc.cluster.local:9092
```

This maps to the `KAFKA_BOOTSTRAP_SERVERS` env var set on every service deployment. The existing default of `localhost:9092` is for local dev; K8s deployments override it.

---

## 4. Key Configuration Decisions

| Setting | Value | Rationale |
|---|---|---|
| KRaft mode (no ZK) | Combined controller+broker | Simpler ops, fewer pods, officially recommended |
| `acks=all` | Already set in all producers | Durability — with RF=1 this means the single broker acks (ready for RF=3 in prod) |
| `min.insync.replicas=1` | Cluster-wide | MVP single broker; raise to 2 with RF=3 in production |
| `replication.factor=1` | All topics | MVP single broker; raise to 3 in production |
| `compression.type=producer` | Broker-level | Honour the `gzip` compression set by all producers |
| `log.retention.hours=168` | 7 days | Sufficient for reprocessing; long-term retention is in S3 |
| `enable.auto.commit=false` | All consumers | Already set — manual commit after processing for at-least-once |
| `log.segment.bytes=1GB` | Default | Reasonable for this workload |

---

## 5. Local Development (docker-compose)

Single-broker KRaft instance for local `pytest` and manual testing:

```yaml
# infrastructure/kafka/docker-compose.yml
services:
  kafka:
    image: apache/kafka:4.1.1
    ports:
      - "9092:9092"
    environment:
      KAFKA_NODE_ID: 1
      KAFKA_PROCESS_ROLES: broker,controller
      KAFKA_CONTROLLER_QUORUM_VOTERS: 1@kafka:9093
      KAFKA_LISTENERS: PLAINTEXT://:9092,CONTROLLER://:9093,EXTERNAL://:19092
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092,EXTERNAL://localhost:19092
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: PLAINTEXT:PLAINTEXT,CONTROLLER:PLAINTEXT,EXTERNAL:PLAINTEXT
      KAFKA_INTER_BROKER_LISTENER_NAME: PLAINTEXT
      KAFKA_CONTROLLER_LISTENER_NAMES: CONTROLLER
      KAFKA_LOG_DIRS: /tmp/kafka-logs
      KAFKA_NUM_PARTITIONS: 1
      KAFKA_DEFAULT_REPLICATION_FACTOR: 1
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
      KAFKA_GROUP_INITIAL_REBALANCE_DELAY_MS: 0
      CLUSTER_ID: MkU3OEVBNTcwNTJENDM2Qk
    volumes:
      - kafka-data:/tmp/kafka-logs

  kafka-init:
    image: apache/kafka:4.1.1
    depends_on:
      kafka:
        condition: service_started
    entrypoint: ["/bin/bash", "/scripts/create-topics.sh"]
    environment:
      KAFKA_BOOTSTRAP: kafka:9092
    volumes:
      - ./scripts:/scripts:ro

volumes:
  kafka-data:
```

External listener on `localhost:19092` allows services running on the host (outside Docker) to connect.

---

## 6. Networking and Security

### Network Policy

Restrict Kafka to only namespaces that need it:

```yaml
ingress:
  - from:
      - namespaceSelector:
          matchLabels:
            umbrella-kafka-access: "true"
    ports:
      - port: 9092
```

Label the allowed namespaces: `umbrella-connectors`, `umbrella-ingestion`, `umbrella-processing`, `umbrella-storage`, `umbrella-ui`.

### Future: mTLS / SASL

For production, add SASL/SCRAM or mTLS listeners. This is deferred — the current architecture uses `PLAINTEXT` within the cluster, which is standard for in-cluster K8s communication behind NetworkPolicy.

---

## 7. Monitoring

### JMX Metrics

Enable JMX on each broker via env vars:
```
KAFKA_JMX_PORT: 9101
KAFKA_JMX_OPTS: -Dcom.sun.management.jmxagent.authenticate=false ...
```

### PodMonitor (Prometheus)

Scrape JMX exporter sidecar or the built-in metrics endpoint. Key metrics:
- `kafka_server_BrokerTopicMetrics_MessagesInPerSec` — message throughput
- `kafka_server_ReplicaManager_UnderReplicatedPartitions` — replication health
- `kafka_consumer_consumer_fetch_manager_metrics_records_lag_max` — consumer lag (per consumer group)
- `kafka_log_Log_Size` — disk usage per partition

### Grafana Dashboard

Deploy a standard Kafka dashboard (e.g., Strimzi or Confluent community) to `umbrella-infra` namespace.

---

## 8. File Inventory

Files to create:

```
infrastructure/kafka/
  Dockerfile
  docker-compose.yml
  scripts/
    create-topics.sh

deploy/k8s/umbrella-streaming/
  namespace.yaml
  configmap.yaml
  statefulset.yaml
  service-headless.yaml
  service.yaml
  job-create-topics.yaml
  networkpolicy.yaml
  podmonitor.yaml
```

---

## 9. Implementation Order

1. **`infrastructure/kafka/scripts/create-topics.sh`** — idempotent topic creation script
2. **`infrastructure/kafka/Dockerfile`** — thin wrapper adding scripts
3. **`infrastructure/kafka/docker-compose.yml`** — local dev single-broker
4. **Verify locally** — `docker compose up`, produce/consume test messages with `kafka-console-producer.sh` / `kafka-console-consumer.sh`
5. **`deploy/k8s/umbrella-streaming/namespace.yaml`**
6. **`deploy/k8s/umbrella-streaming/configmap.yaml`** — shared config + topic creation script
7. **`deploy/k8s/umbrella-streaming/statefulset.yaml`** — single-broker KRaft instance
8. **`deploy/k8s/umbrella-streaming/service-headless.yaml`** + **`service.yaml`**
9. **`deploy/k8s/umbrella-streaming/job-create-topics.yaml`** — topic creation Job
10. **`deploy/k8s/umbrella-streaming/networkpolicy.yaml`** — lock down access
11. **`deploy/k8s/umbrella-streaming/podmonitor.yaml`** — Prometheus scraping
12. **Integration test** — deploy to dev cluster, point existing services at `kafka.umbrella-streaming.svc:9092`, verify end-to-end flow

---

## 10. Validation Checklist

- [ ] `docker compose up` starts single-broker Kafka, topics auto-created
- [ ] Existing services connect with `localhost:19092` (local) or `kafka.umbrella-streaming.svc:9092` (K8s)
- [ ] All 7 topics created with partition=1, replication-factor=1
- [ ] Producer `acks=all` + broker `min.insync.replicas=1` confirmed
- [ ] Consumer groups (`email-processor`, `ingestion-normalizer`) show zero lag after processing
- [ ] NetworkPolicy blocks access from unlabelled namespaces
- [ ] JMX metrics visible in Prometheus
