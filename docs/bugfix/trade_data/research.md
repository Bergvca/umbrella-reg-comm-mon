# Bug: Trade Data Events Not Showing as Trades

## Problem

1. Not all `trade_data` events are shown as trades when searching messages
2. Only the test trade (from `test-pipeline-minikube.sh`) appears in the trade blotter

## Root Cause

**The ingestion service publishes ALL normalized messages — including trades — to the `normalized-messages` Kafka topic. But the Logstash trades pipeline reads from `normalized-trades`.** Trade data therefore ends up in the `messages-*` ES index instead of the `trades-*` index.

### What happens now

```
Ingestion / Demo script
  → normalized-messages topic
    → Logstash messages pipeline → messages-*.month index  (WRONG for trades)

Test script (test-pipeline-minikube.sh)
  → normalized-trades topic
    → Logstash trades pipeline → trades-*.month index      (CORRECT)
```

The UI trade blotter queries `trades-*`, so only the test trade (which was explicitly published to `normalized-trades`) is visible. All other trade_data messages land in `messages-*` and are invisible to the trade blotter.

### What should happen

```
trade_data messages → normalized-trades topic → Logstash trades pipeline → trades-*.month
all other messages  → normalized-messages topic → Logstash messages pipeline → messages-*.month
```

## Files to Fix

### Ingestion Layer (route trade_data to the correct Kafka topic)

| File | Why |
|------|-----|
| `ingestion-api/umbrella_ingestion/config.py` | Add a `trades_output_topic` config field (default `normalized-trades`) |
| `ingestion-api/umbrella_ingestion/service.py` | After normalization, publish `Channel.TRADE_DATA` messages to the trades topic instead of the default output topic |

### Demo Data Script (publish demo trades to the correct topic)

| File | Why |
|------|-----|
| `scripts/demo-data/generate_demo_data.py` | Ensure generated trade_data messages target the `normalized-trades` topic |
| `scripts/demo-regcomm-usecase.sh` | Publish trade messages to `normalized-trades` instead of `normalized-messages` |

### Verify / No Changes Expected (but review)

| File | Purpose |
|------|---------|
| `infrastructure/logstash/pipeline/trades.conf` | Already reads from `normalized-trades` — OK |
| `infrastructure/logstash/pipeline/messages.conf` | Reads from `normalized-messages` — OK (trades will stop arriving here once routed correctly) |
| `deploy/k8s/umbrella-streaming/configmap.yaml` | Already creates `normalized-trades` topic — OK |
| `infrastructure/elasticsearch/config/index-templates/trades-template.json` | Trades index template — OK |
| `ui/backend/umbrella_ui/routers/trades.py` | Queries `trades-*` — OK |
| `ui/backend/umbrella_ui/routers/messages.py` | Queries `messages-*` — OK |
| `ui/backend/umbrella_ui/es/queries.py` | Trade search query builders — OK |
| `ingestion-api/umbrella_ingestion/normalizers/trade_data.py` | Normalizer implementation — OK |
| `ingestion-api/umbrella_ingestion/normalizers/__init__.py` | Registration — OK |

## Evidence

- **`service.py:192`** — all channels publish to `self._config.kafka.output_topic` (= `normalized-messages`), no special routing for trades
- **`trades.conf:4`** — `topics => ["normalized-trades"]`
- **`messages.conf:4`** — `topics => ["normalized-messages", "processing-results"]`
- **`test-pipeline-minikube.sh:376-384`** — test trade explicitly published to `normalized-trades` (this is why it works)
- **`demo-regcomm-usecase.sh:377`** — demo trades published to `normalized-messages` (this is why they don't show up as trades)
- **`trades.py:66`** — trade blotter queries `trades-*` index
- **`configmap.yaml:52`** — `normalized-trades` topic is already created in K8s
