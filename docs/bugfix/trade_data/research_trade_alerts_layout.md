# Research: Trade Data Alerts Showing in Regular Message Layout

## Problem

When clicking a trade alert (e.g. `/alerts/<id>`), the page uses the same generic `AlertDetailPage` layout as communication alerts. The user expects trade alerts to reuse the layout from the trade blotter detail page (e.g. `/trades/trades-2026.03/EX-TEST-TRADE-001`).

## Root Cause

This is a **frontend layout issue**, not a data/routing issue. The backend correctly identifies trade alerts and returns the `trade` field in the API response. The `AlertDetailPage` does conditionally render `<TradeDisplay>` for trade alerts — but it wraps it in the same two-column layout (content left, `AlertSidePanel` right) used for message alerts. The `TradeDetailPage` has a distinct layout with breadcrumbs, a linked-alerts sidebar, and different spacing that should be reused.

## Backend — Confirmed Working

The data pipeline is correct:
- **Ingestion** (`ingestion-api/umbrella_ingestion/service.py:233-236`): Routes `Channel.TRADE_DATA` to `trades-{YYYY.MM}` ES index
- **Percolator** (`ingestion-api/umbrella_ingestion/percolator.py:76-165`): Stores the correct `es_index` in PostgreSQL
- **`get_alert()` endpoint** (`ui/backend/umbrella_ui/routers/alerts.py:206-255`): Checks `alert.es_index.startswith("trades-")`, fetches from the correct index, populates `trade: ESTrade` on the response
- **Schema** (`ui/backend/umbrella_ui/schemas/alert.py`): `AlertWithMessage` has both `message: ESMessage | None` and `trade: ESTrade | None`

No backend changes needed for the detail view.

## Frontend — Layout Comparison

### Current: AlertDetailPage (`ui/frontend/src/pages/AlertDetailPage.tsx`)

- Generic two-column layout for ALL alert types
- Left: `<TradeDisplay>` or `<MessageDisplay>` (correctly branches on `alert.trade` at line 91)
- Right: `<AlertSidePanel>` (alert metadata, decisions, status)
- Navigation: "Back to Alerts" link + prev/next alert buttons
- No breadcrumbs, no trade-specific context

### Target: TradeDetailPage (`ui/frontend/src/pages/TradeDetailPage.tsx`)

- Trade-specific layout with breadcrumbs (`Trades > {ticker} / {docId}`)
- Left: `<TradeDisplay trade={trade} />`
- Right: Linked alerts sidebar showing severity/status badges per alert
- Uses `<Breadcrumb>` components
- Different spacing (`space-y-6 max-w-4xl`)

### Shared Component: TradeDisplay (`ui/frontend/src/components/trades/TradeDisplay.tsx`)

Already used by both pages. Renders:
- Header with ticker, buy/sell badge, timestamp
- Summary card (body_text)
- Trade Details grid (ticker, side, quantity, price, notional, currency, order type, venue, asset class, execution ID, order ID, account, settlement date, direction)
- Participants card (trader + counterparty with entity links)

## Fix Required

The `AlertDetailPage` needs to detect trade alerts and render with the `TradeDetailPage` layout instead of the generic message-alert layout. Specifically:

1. **When `alert.trade` is present**, render using the trade blotter layout:
   - Breadcrumbs: `Alerts > {alert name or ticker}`
   - `<TradeDisplay>` for the left panel
   - Alert metadata sidebar (keep `AlertSidePanel` for decisions/status, but style it like the `TradeDetailPage` linked-alerts sidebar)

2. **When `alert.message` is present**, keep the current message layout unchanged.

### Files to Modify

| File | Change |
|------|--------|
| `ui/frontend/src/pages/AlertDetailPage.tsx` | Add trade-specific layout branch that mirrors `TradeDetailPage` layout while keeping alert-specific controls (decisions, status, prev/next navigation) |

### Files for Reference (no changes needed)

| File | Why |
|------|-----|
| `ui/frontend/src/pages/TradeDetailPage.tsx` | Layout to replicate for trade alerts |
| `ui/frontend/src/components/trades/TradeDisplay.tsx` | Already shared, no changes needed |
| `ui/frontend/src/components/alerts/AlertSidePanel.tsx` | Alert metadata panel — keep as-is |
| `ui/backend/umbrella_ui/routers/alerts.py` | Backend already returns `trade` field correctly |
| `ui/backend/umbrella_ui/schemas/alert.py` | Schema already supports `trade` field |
| `ui/frontend/src/lib/types.ts` | `AlertWithMessage` type already has `trade?: TradeRecord` |

## Secondary Issue: list_alerts() Batch Fetch

Separate from the layout bug, `list_alerts()` (`ui/backend/umbrella_ui/routers/alerts.py:174`) only batch-fetches from `messages-*`, so trade alert document previews are missing in the alerts list. This is a separate fix:
- Partition refs by index type (`trades-*` vs `messages-*`)
- Batch-fetch from both index patterns
- This does NOT affect the detail page layout issue
