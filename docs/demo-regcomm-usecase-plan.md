# Plan: Regulatory Communications Monitoring Demo

## Prerequisites

- `scripts/deploy-minikube.sh` and `scripts/test-pipeline-minikube.sh` have both run successfully (DB roles, test user, entity schema, Kafka topics, Logstash pipeline all in place)

---

## Part A: Demo Script (`scripts/demo-regcomm-usecase.sh` + `scripts/demo-data/generate_demo_data.py`)

### Fraud Scenario: Front-Running / Insider Trading

**Narrative:** Trader **Marcus Webb** at Acme Capital receives advance tip-offs from **Sarah Chen** (analyst at Aurora Partners) about an upcoming acquisition of **Meridian Technologies** (ticker: MRDN). They communicate across email, Teams chat, and phone calls using coded language. Marcus places large trades ahead of the public announcement, then takes profits the day after.

### Characters

| Person | Role | Handles |
|--------|------|---------|
| Marcus Webb | Trader, Acme Capital | `marcus.webb@acme-capital.com`, `mwebb@teams.acme-capital.com` |
| Sarah Chen | Analyst, Aurora Partners | `sarah.chen@aurora-partners.com`, `schen@bloomberg.net` |
| David Park | Marcus's manager | `david.park@acme-capital.com` |
| Lisa Torres | Compliance officer | `lisa.torres@acme-capital.com` |
| Rachel Kim | Client relationship mgr | `rachel.kim@acme-capital.com` |

### Timeline

All data uses a consistent 5-day window:

```
Day 1 (Mon):  Normal emails, team standup, Sarah's first vague email
Day 2 (Tue):  Chat between Marcus & Sarah (coded), first large MRDN trade (5,000 shares)
Day 3 (Wed):  Coded email exchange, options purchase (200 contracts), suspicious call #1
Day 4 (Thu):  "Thursday after close" chat, more MRDN buys (10k + 3k), suspicious call #2
Day 5 (Fri):  M&A announcement, profit-taking trades, forward to personal email (off-channel)
```

### Data Breakdown

#### 1. Emails (~20) — sent via SMTP through real pipeline

**Normal business emails (~14):**
- David → team: Weekly standup recap
- Lisa → all: Quarterly compliance training reminder
- Rachel → Marcus: Client portfolio review notes
- IT dept → all: System maintenance window notice
- Marcus → David: Q1 PnL summary
- David → Marcus: "Good numbers, keep it up"
- Lisa → all: Updated personal trading policy
- Rachel → team: Client dinner logistics
- Marcus → Rachel: Confirming attendance
- External newsletter: Market morning briefing
- David → team: Offsite planning
- Marcus → David: Travel expense report
- Lisa → Marcus: Routine pre-clearance approval
- Rachel → Marcus: New client onboarding docs

**Suspicious emails (~6):**
1. Sarah → Marcus: "Catching up — had some interesting findings on the Meridian tech stack research" (vague initial hint, Day 1)
2. Marcus → Sarah: "Thanks for sharing that — the tech sector is definitely heating up" (acknowledgment, Day 1)
3. Sarah → Marcus: "The weather is about to change for our favorite company. Repositioning recommended." (coded, Day 3)
4. Marcus → Sarah: "Garden fully repositioned. Appreciate the forecast." (coded trade confirmation, Day 3)
5. Sarah → Marcus: Subject "Meridian_Strategic_Analysis_CONFIDENTIAL.pdf" — "Here's that research — please keep between us" (Day 4)
6. Marcus → `marcus.personal@gmail.com`: FWD of Sarah's Meridian analysis with "Saving for my records" (off-channel attempt, Day 5)

#### 2. Teams Chat messages (~12) — published to `normalized-messages` Kafka topic

**Normal chats (~6):**
- Marcus ↔ David: "Morning, any updates on the Henderson account?"
- Marcus ↔ Rachel: "Lunch at 12:30? The Italian place?"
- David → team channel: "Reminder: P&L reports due by EOD Friday"
- Marcus → IT helpdesk: "My Bloomberg terminal is freezing again"
- Rachel ↔ Marcus: "Client wants to move the meeting to 3pm"
- David ↔ Lisa: "Can you send me the updated trading policy?"

**Suspicious chats (~6):**
1. Marcus → Sarah: "Project Aurora — still on track?" (Day 2)
2. Sarah → Marcus: "Absolutely. The board meets Thursday after close. You didn't hear it from me." (Day 2)
3. Marcus → Sarah: "Understood. I'll be ready." (Day 2)
4. Marcus → Sarah: "How confident are we? I'm thinking of going big." (Day 4)
5. Sarah → Marcus: "Very. The numbers are incredible. This will move the market." (Day 4)
6. Marcus → Sarah: "Already loaded up. Full position. Thanks for everything." (Day 4)

#### 3. Trade Data (~8 records) — published to `normalized-messages` as `channel=trade_data`

Trade data uses the NormalizedMessage schema with:
- `participants`: trader (role=`trader`), counterparty/broker (role=`counterparty`)
- `body_text`: human-readable trade summary (e.g. "BUY 5,000 MRDN @ $45.20 via DMA")
- `metadata`: structured trade fields (`ticker`, `side`, `quantity`, `price`, `order_type`, `venue`, `execution_id`, `asset_class`, `account_id`)

| Day | Side | Ticker | Qty | Price | Notes |
|-----|------|--------|-----|-------|-------|
| 1 (Mon) | BUY | MRDN | 500 | $44.10 | Small starter position (before any tips) |
| 2 (Tue) | BUY | MRDN | 5,000 | $45.20 | Spike after Sarah's first coded chat |
| 3 (Wed) | BUY | MRDN Apr $50 Call | 200 contracts | $2.15 | Aggressive options bet |
| 3 (Wed) | BUY | MRDN | 8,000 | $45.80 | Building position |
| 4 (Thu AM) | BUY | MRDN | 10,000 | $46.50 | Largest order, day before announcement |
| 4 (Thu PM) | BUY | MRDN | 3,000 | $46.90 | Final accumulation |
| 5 (Fri) | SELL | MRDN | 26,500 | $62.30 | Dump entire equity position post-announcement |
| 5 (Fri) | SELL | MRDN Apr $50 Call | 200 contracts | $14.80 | Close options at ~7x profit |

#### 4. Call Transcriptions (~3) — published to `normalized-messages` with `audio_ref`

**Call 1 (innocent, Day 1):** Marcus ↔ Rachel, 6 min
- Discussing upcoming client meeting prep, portfolio allocation, nothing suspicious

**Call 2 (suspicious, Day 3):** Marcus ↔ Sarah, 4 min
- Speaker-diarized transcript with coded language:
  - Sarah: "That opportunity we discussed — the timeline just accelerated"
  - Marcus: "How accelerated?"
  - Sarah: "Days, not weeks. Move before the window closes."
  - Marcus: "I'll take care of it today."

**Call 3 (suspicious, Day 4):** Marcus ↔ unknown external, 2 min
- Marcus: "It's done. I'm in for the full amount."
- Unknown: "Good. Just make sure there's no paper trail."
- Marcus: "Understood."

### Alert Rules (seeded into PostgreSQL)

**Risk Model:** "Market Abuse Detection"

**Policy 1: Insider Trading Indicators** (HIGH severity)
- Rule: `body_text:(confidential AND (meridian OR MRDN OR acquisition))`
- Rule: `body_text:("didn't hear it from me" OR "don't tell anyone" OR "keep between us" OR "no paper trail")`
- Rule: `body_text:("repositioned" AND ("weather" OR "garden" OR "forecast"))`

**Policy 2: Unusual Trading Patterns** (MEDIUM severity)
- Rule: `metadata.ticker:MRDN AND metadata.quantity:>=5000`

**Policy 3: Off-Channel Communication** (MEDIUM severity)
- Rule: `body_text:(forward OR "personal email" OR "saving for my records") AND metadata.subject:(*confidential* OR *meridian*)`

### Script Flow

```
demo-regcomm-usecase.sh
│
├─ Step 0: Verify prerequisites (namespaces exist, test user present)
│
├─ Step 1: Seed entities via UI API
│   └─ Create 5 entities with handles (same pattern as test-pipeline-minikube.sh Step 2b)
│
├─ Step 2: Seed alert rules via PostgreSQL
│   └─ INSERT risk_model, policies, rules
│
├─ Step 3: Sync percolator rules
│   └─ Hit UI backend endpoint to sync rules to ES percolator index
│
├─ Step 4: Send emails via SMTP (through real pipeline)
│   └─ kubectl run pod with python smtplib, loop through ~20 emails
│
├─ Step 4b: Create trades-* index template in ES (if not already present)
│   └─ PUT _index_template/trades via ES API
│
├─ Step 5: Publish chats + trades + calls to Kafka
│   └─ kubectl run pod with kafka-console-producer
│   └─ Chats + calls → normalized-messages topic (→ Logstash → messages-*)
│   └─ Trades → normalized-trades topic (→ Logstash → trades-*)
│
├─ Step 6: Wait for pipeline processing (~60s)
│
├─ Step 7: Verify & report
│   ├─ ES document counts by channel (email, teams_chat, trade_data, teams_calls)
│   ├─ Alert count from PostgreSQL
│   ├─ Cross-channel entity summary for Marcus Webb
│   └─ Print summary table
```

### File Structure

```
scripts/
├─ demo-regcomm-usecase.sh            # Orchestrator (bash)
└─ demo-data/
   └─ generate_demo_data.py           # Generates all JSON payloads
                                      # (emails as dicts for smtplib, chats/trades/calls as NormalizedMessage JSON)
```

`generate_demo_data.py` outputs JSON to stdout with sections:
```json
{
  "emails": [ ... ],           // dicts with from, to, subject, body, date, message_id
  "normalized_messages": [ ... ] // NormalizedMessage JSON for chats, trades, calls
}
```

The bash script reads this, sends emails via SMTP pod, and pipes normalized messages to Kafka.

---

## Part B: Trade Data — Global Plan

Adding `trade_data` as a first-class channel requires changes across multiple layers. The demo script (Part A) works by publishing NormalizedMessage JSON directly to Kafka with `channel: "trade_data"`, which Logstash indexes into `messages-*`. This gets trade data searchable immediately. The items below make trade data a proper, production-grade channel.

### B1. Schema Layer

| File | Change |
|------|--------|
| `connectors/connector-framework/umbrella_schema/normalized_message.py` | Add `TRADE_DATA = "trade_data"` to `Channel` enum |

**NormalizedMessage field mapping for trades:**
- `message_id` → unique execution/order ID
- `channel` → `trade_data`
- `direction` → `outbound` (firm selling), `inbound` (firm buying), or `internal` (internal transfer)
- `timestamp` → trade execution timestamp
- `participants[0]` → trader (role=`trader`)
- `participants[1]` → counterparty/broker (role=`counterparty`)
- `body_text` → human-readable summary: `"BUY 5,000 MRDN @ $45.20 via DMA"`
- `metadata` → structured trade fields:
  ```json
  {
    "ticker": "MRDN",
    "side": "buy",
    "quantity": 5000,
    "price": 45.20,
    "notional": 226000.00,
    "currency": "USD",
    "order_type": "limit",
    "venue": "NYSE",
    "execution_id": "EX-2026-00142",
    "asset_class": "equity",
    "account_id": "ACME-PROP-001",
    "settlement_date": "2026-03-18",
    "order_id": "ORD-2026-00098"
  }
  ```

### B2. Connector + Normalizer

| Component | What |
|-----------|------|
| `connectors/trade-data/` | New connector package: `umbrella-trade-connector`. Polls OMS/EMS feeds (FIX, CSV drop, REST API). Publishes `RawMessage` to `raw-messages` topic. |
| `ingestion-api/umbrella_ingestion/normalizers/trade_data.py` | `TradeDataNormalizer(BaseNormalizer)` — maps parsed trade records to `NormalizedMessage`. Computes `direction` from side + account type. Builds `body_text` summary. |
| `ingestion-api/umbrella_ingestion/service.py` | Register `TradeDataNormalizer` in the `NormalizerRegistry` |

### B3. Elasticsearch

| File | Change |
|------|--------|
| `infrastructure/elasticsearch/config/index-templates/trades-template.json` | **New template** for `trades-*` index pattern. Top-level typed fields for ticker, side, quantity, price, notional, currency, venue, asset_class, order_type, account_id, execution_id, settlement_date. Plus shared fields (message_id, channel, direction, timestamp, participants). Separate ILM policy (`umbrella-trades-retention`) with its own rollover/retention settings. |
| `infrastructure/logstash/pipeline/trades.conf` | **New pipeline** — consumes from a `normalized-trades` Kafka topic (or filters `channel == "trade_data"` from `normalized-messages`) and writes to `trades-YYYY.MM` index. |

**Decision:** Trades get a separate `trades-*` index (not `messages-*`). Trade data is high-volume with different retention/aggregation needs. Cross-channel correlation is done at the application layer via entity IDs and time windows, not by co-locating in the same index.

### B4. UI Backend

| File | Change |
|------|--------|
| `ui/backend/umbrella_ui/es/models.py` | Add `ESTradeMetadata` model with typed fields (ticker, side, quantity, price, etc.). Conditionally parse when `channel == "trade_data"`. |
| `ui/backend/umbrella_ui/es/queries.py` | Add trade-specific filters: ticker, side, quantity range, price range, date range, account. New endpoint or extend existing search with trade filters. |
| `ui/backend/umbrella_ui/routers/messages.py` | Add query params for trade filters (or create a separate `/api/v1/trades/search` router). |
| `ui/backend/umbrella_ui/routers/trades.py` | **New file** — dedicated trade search + aggregation endpoints: trade timeline, volume by ticker, P&L calculation, trade-around-communication correlation. |
| `ui/backend/umbrella_ui/schemas/trade.py` | **New file** — Pydantic response schemas for trade search results, trade detail, trade aggregations. |

### B5. UI Frontend

| Component | What |
|-----------|------|
| `ui/frontend/src/lib/constants.ts` | Add `"trade_data"` to `CHANNELS` array |
| `ui/frontend/src/lib/types.ts` | Add `TradeRecord` type with typed trade metadata fields |
| `ui/frontend/src/pages/TradesPage.tsx` | **New page** — trade blotter view with sortable columns (time, ticker, side, qty, price, venue), filters, and pagination |
| `ui/frontend/src/pages/TradeDetailPage.tsx` | **New page** — single trade detail view showing: trade metadata, linked communications (messages from same trader within ±24h window), linked alerts, entity profile link |
| `ui/frontend/src/components/trades/TradeBlotter.tsx` | **New component** — data table with columns for all trade fields, color-coded buy/sell, sortable |
| `ui/frontend/src/components/trades/TradeTimeline.tsx` | **New component** — visual timeline showing trades + communications on a shared time axis for a given entity. This is the key cross-correlation view. |
| `ui/frontend/src/components/trades/TradeVolumeChart.tsx` | **New component** — bar/line chart showing trade volume over time for a ticker, overlaid with alert markers |
| `ui/frontend/src/components/messages/MessageDetailPage.tsx` | Extend to show "Related Trades" section when viewing a message whose participants also have trades in the same time window |
| `ui/frontend/src/api/trades.ts` | **New file** — API client for trade search, detail, aggregations |
| `ui/frontend/src/hooks/useTrades.ts` | **New file** — React Query hooks for trade data |
| App router | Add routes: `/trades`, `/trades/:index/:id` |

### B6. Agent Tools

| File | Change |
|------|--------|
| `agents/umbrella_agents/tools/trade_search.py` | **New tool** — allows agents to search trades by ticker, trader, date range, quantity thresholds. Used by the Trade Surveiller agent. |
| `agents/umbrella_agents/tools/trade_correlation.py` | **New tool** — given a communication message, finds trades by the same entity within a configurable time window. Core tool for cross-channel surveillance. |

### B7. Alert Rules for Trade Surveillance

Trade-specific percolator rules need access to top-level trade fields (ticker, quantity, side, etc.) in the `trades-*` index. Since trades have their own index template (B3), these fields are mapped as top-level typed fields, making them directly usable in percolator queries. The percolator index (`umbrella-alert-rules`) needs the trade field mappings added so it can validate trade-targeting rules.

**Example rules:**
- Large order: `channel:trade_data AND metadata.quantity:>=10000`
- Concentrated position: aggregation-based (not percolator — needs a scheduled agent)
- Trade-around-news: requires correlation with external news feed (future)
- Wash trading: same ticker, buy+sell within short window, same entity (scheduled agent)

### B8. Implementation Order

```
Phase 1 (Demo):     Add TRADE_DATA to Channel enum
                     Create trades-* ES index template
                     Logstash pipeline (or demo script) routes trades to trades-* index
                     Demo script publishes trade data to Kafka
                     → This is what Part A delivers

Phase 2 (Backend):   Trade normalizer + connector stub
                     ES template updates for trade metadata fields
                     Backend trade search endpoint + filters
                     Trade-specific alert rules

Phase 3 (Frontend):  TradesPage + TradeDetailPage
                     TradeBlotter component
                     TradeTimeline cross-correlation view
                     Related Trades on MessageDetailPage

Phase 4 (Agents):    trade_search tool
                     trade_correlation tool
                     Trade Surveiller agent configuration
```

---

## What the Demo Proves

After running `demo-regcomm-usecase.sh`, a reviewer can:

1. **Search by channel** — filter messages by email, teams_chat, trade_data, or teams_calls
2. **See alerts fire** — percolator rules catch suspicious keywords and large trades
3. **Cross-reference entity** — search for "Marcus Webb" and see activity across all 4 channels
4. **Spot the pattern** — trades spike exactly when coded communications occur
5. **Review the timeline** — Day 1 innocent → Day 2 first tip → Day 3-4 heavy trading → Day 5 profit-taking
6. **Off-channel detection** — the personal email forward is flagged
7. **Audio correlation** — call transcripts with suspicious phrases appear alongside the trades
