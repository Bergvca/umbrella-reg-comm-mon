# Fix Plan: Route Trade Data to `normalized-trades` Kafka Topic

## Problem

All normalized messages (including trades) are published to `normalized-messages`. Logstash routes `normalized-messages` → `messages-*` and `normalized-trades` → `trades-*`. Since trades never reach `normalized-trades`, they end up in `messages-*` and are invisible to the trade blotter (which queries `trades-*`).

## Changes

### 1. Add `trades_output_topic` to Kafka config

**File:** `ingestion-api/umbrella_ingestion/config.py`

Add a new field to `KafkaConsumerConfig`:

```python
trades_output_topic: str = Field(
    default="normalized-trades",
    description="Kafka topic to publish normalized trade messages to",
)
```

This keeps the default topic configurable via `KAFKA_TRADES_OUTPUT_TOPIC` env var, consistent with the existing pydantic-settings pattern.

### 2. Route trade messages to the trades topic in the ingestion service

**File:** `ingestion-api/umbrella_ingestion/service.py`

In `_dual_write`, select the output topic based on the channel:

```python
from umbrella_schema import Channel

# In _dual_write, replace the hardcoded topic:
topic = (
    self._config.kafka.trades_output_topic
    if normalized.channel == Channel.TRADE_DATA
    else self._config.kafka.output_topic
)
await self._producer.send_and_wait(topic, value=value, key=key)
```

Also update the percolator ES index in `_dual_write` — trades should use `trades-{YYYY.MM}` not `messages-{YYYY.MM}`:

```python
if normalized.channel == Channel.TRADE_DATA:
    es_index = f"trades-{normalized.timestamp:%Y.%m}"
else:
    es_index = f"messages-{normalized.timestamp:%Y.%m}"
```

### 3. Publish demo trades to the correct Kafka topic

**File:** `scripts/demo-regcomm-usecase.sh`

The script currently publishes ALL normalized messages (chats, trades, calls) to `normalized-messages` in a single `kafka-console-producer` call (line 377). Split this into two producer calls:

1. Filter out `trade_data` messages → publish to `normalized-messages`
2. Filter `trade_data` messages → publish to `normalized-trades`

Replace the single producer block (lines 370-377) with:

```bash
# Non-trade messages → normalized-messages
NON_TRADE_LINES=$(echo "$DEMO_DATA" | jq -c '.normalized_messages[] | select(.channel != "trade_data")')
echo "$NON_TRADE_LINES" | kubectl run demo-kafka-producer --rm -i \
  --image=apache/kafka:4.1.1 -n umbrella-streaming --restart=Never -- \
  /opt/kafka/bin/kafka-console-producer.sh \
  --bootstrap-server kafka:9092 \
  --topic normalized-messages

# Trade messages → normalized-trades
TRADE_LINES=$(echo "$DEMO_DATA" | jq -c '.normalized_messages[] | select(.channel == "trade_data")')
kubectl delete pod demo-kafka-producer -n umbrella-streaming --ignore-not-found 2>/dev/null || true
echo "$TRADE_LINES" | kubectl run demo-kafka-producer --rm -i \
  --image=apache/kafka:4.1.1 -n umbrella-streaming --restart=Never -- \
  /opt/kafka/bin/kafka-console-producer.sh \
  --bootstrap-server kafka:9092 \
  --topic normalized-trades
```

### 4. Update demo verification to check `trades-*` index

**File:** `scripts/demo-regcomm-usecase.sh`

The verification step (line 412) counts trade documents in `messages-*`. Change it to query `trades-*`:

```bash
ES_TRADE_COUNT=$(curl -s "http://localhost:9200/trades-*/_count" \
    -H "Content-Type: application/json" \
    -d '{"query":{"match_all":{}}}' 2>/dev/null | jq -r '.count // 0')
```

### 5. Add/update tests

**File:** `ingestion-api/tests/test_service.py` (new or existing)

Add a test that verifies `_dual_write` sends `Channel.TRADE_DATA` messages to `trades_output_topic` and other channels to `output_topic`. Mock the Kafka producer and assert `send_and_wait` is called with the correct topic for each channel.

## Files NOT changed (verified OK)

| File | Reason |
|------|--------|
| `infrastructure/logstash/pipeline/trades.conf` | Already reads from `normalized-trades` |
| `infrastructure/logstash/pipeline/messages.conf` | Already reads from `normalized-messages` |
| `deploy/k8s/umbrella-streaming/configmap.yaml` | Already creates `normalized-trades` topic |
| `infrastructure/elasticsearch/config/index-templates/trades-template.json` | Template is correct |
| `ui/backend/umbrella_ui/routers/trades.py` | Already queries `trades-*` |
| `ingestion-api/umbrella_ingestion/normalizers/trade_data.py` | Normalizer logic is correct |
| `scripts/demo-data/generate_demo_data.py` | Data generation is correct — routing is the caller's responsibility |

## Order of implementation

1. `config.py` — add the new field (no behavioral change yet)
2. `service.py` — add topic routing + ES index routing
3. Tests — verify routing logic
4. `demo-regcomm-usecase.sh` — split Kafka publishing + fix verification query
5. Deploy and re-run the demo script to confirm trades appear in the trade blotter
