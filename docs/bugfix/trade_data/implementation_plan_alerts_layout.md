# Implementation Plan: Trade Alerts Layout Fix

**Source:** `docs/bugfix/trade_data/research_trade_alerts_layout.md`

## Overview

Two issues need fixing:
1. **Primary:** Trade alert detail page uses the generic message-alert layout instead of the trade blotter layout
2. **Secondary:** `list_alerts()` only batch-fetches from `messages-*`, so trade alert previews are missing in the alerts list

---

## Issue 1: AlertDetailPage Trade Layout

### Goal

When `alert.trade` is present, render the `AlertDetailPage` with the same layout style as `TradeDetailPage` (breadcrumbs, `space-y-6 max-w-4xl` container, trade-focused sidebar) while keeping alert-specific controls (decisions, status, prev/next navigation).

### File to modify

`ui/frontend/src/pages/AlertDetailPage.tsx`

### Changes

1. **Add breadcrumb imports** — Import `Breadcrumb`, `BreadcrumbItem`, `BreadcrumbLink`, `BreadcrumbList`, `BreadcrumbPage`, `BreadcrumbSeparator` from `@/components/ui/breadcrumb`.

2. **Branch the return layout based on `alert.trade`** — After the loading/error guards (unchanged), check if `alert.trade` exists and render a trade-specific layout:

   **Trade alert layout** (when `alert.trade` is truthy):
   ```
   <div className="space-y-6 max-w-4xl">
     <!-- Breadcrumbs: Alerts > {alert.trade.metadata.ticker ?? alert.name} -->
     <Breadcrumb>
       <BreadcrumbList>
         <BreadcrumbItem>
           <BreadcrumbLink href="/alerts">Alerts</BreadcrumbLink>
         </BreadcrumbItem>
         <BreadcrumbSeparator />
         <BreadcrumbItem>
           <BreadcrumbPage>
             {alert.trade.metadata?.ticker ?? alert.name}
           </BreadcrumbPage>
         </BreadcrumbItem>
       </BreadcrumbList>
     </Breadcrumb>

     <!-- Prev/next navigation (same buttons as current, right-aligned) -->

     <div className="flex gap-6 items-start">
       <!-- Left: TradeDisplay -->
       <div className="flex-1 min-w-0">
         <TradeDisplay trade={alert.trade} />
       </div>

       <!-- Right: AlertSidePanel (same as current, w-80) -->
       <div className="w-80 shrink-0 sticky top-0 max-h-[calc(100vh-7rem)] overflow-y-auto">
         <AlertSidePanel ... />
       </div>
     </div>
   </div>
   ```

   **Message alert layout** (when `alert.trade` is falsy): Keep the current layout exactly as-is (the `<div className="p-6">` block with "Back to Alerts" link, two-column with Card-wrapped `MessageDisplay`).

3. **Implementation approach** — Extract the existing return block into a conditional:
   - If `alert.trade`: render trade layout (breadcrumbs, `max-w-4xl`, no Card wrapper around TradeDisplay)
   - Else: render the current message layout unchanged

### Key decisions

- **Keep `AlertSidePanel` for trade alerts** — it contains decision history, decision form, linked entities, and position label. These are alert-specific and should stay.
- **Use `w-80` sidebar width** (same as current) rather than `w-72` from `TradeDetailPage` — the `AlertSidePanel` has more content (decisions form) and needs the wider column.
- **Breadcrumbs replace "Back to Alerts" link** — the breadcrumb `Alerts` link serves the same navigation purpose.
- **Prev/next nav stays** — render the arrow buttons between the breadcrumb and the two-column layout.

---

## Issue 2: list_alerts() Trade Document Batch Fetch

### Goal

Trade alerts in the alerts list should show document preview data (currently only `messages-*` documents are fetched, so trade alerts have no preview).

### File to modify

`ui/backend/umbrella_ui/routers/alerts.py` — `list_alerts()` function (lines 143–203)

### Changes

1. **Partition alert refs by index type** — After fetching alerts from PostgreSQL, split the ES refs into two groups:
   ```python
   message_refs = [r for r in refs if not r["es_index"].startswith("trades-")]
   trade_refs = [r for r in refs if r["es_index"].startswith("trades-")]
   ```

2. **Batch-fetch trades from `trades-*`** — Add a second ES search for trade refs:
   ```python
   trade_lookup: dict[str, ESTrade] = {}
   if trade_refs:
       trade_doc_ids = [ref["es_document_id"] for ref in trade_refs]
       try:
           trade_resp = await es.search(
               index="trades-*",
               body={
                   "query": {"terms": {"message_id": trade_doc_ids}},
                   "size": len(trade_doc_ids),
               },
           )
           for hit in trade_resp.get("hits", {}).get("hits", []):
               try:
                   t = ESTrade.model_validate(hit["_source"])
                   trade_lookup[hit["_source"].get("message_id", hit["_id"])] = t
                   except Exception:
                       pass
       except Exception:
           pass
   ```

3. **Only search `messages-*` for message refs** — Change the existing batch fetch to only use `message_refs`:
   ```python
   if message_refs:
       es_resp = await es.search(index="messages-*", body=build_batch_fetch_messages(message_refs))
       ...
   ```

4. **No schema changes needed for `AlertOut`** — The list view uses `AlertOut` (not `AlertWithMessage`), which doesn't include `message` or `trade` fields. The batch fetch is used for populating preview data.

   **Check:** Verify whether `AlertOut` in the frontend actually uses any ES data in the list view. Looking at the current code, `AlertOut` only has PG fields (`name`, `severity`, `status`, etc.), so the ES batch fetch in `list_alerts()` currently populates `es_lookup` but never attaches it to the response items. This means the batch fetch may be dead code or used for a preview field not yet visible.

   **Action:** If the batch fetch is indeed unused in the response, skip this issue entirely — it has no user-visible impact until a preview field is added to `AlertOut`. If a preview is planned, add `preview_text: str | None = None` to `AlertOut` and populate it from `ESMessage.body_text` or `ESTrade.body_text`.

### Investigation needed before implementing

- Confirm whether `es_lookup` from the batch fetch is actually used anywhere in the `list_alerts` response construction. Currently the code builds `es_lookup` but the `AlertOut` items are constructed purely from `Alert` model fields (lines 187–201). If this is dead code, document it and defer.

---

## Implementation Order

1. **Issue 1 first** (frontend layout) — Single file change, immediately user-visible, no backend dependency
2. **Issue 2 second** (batch fetch) — Investigate whether it has user-visible impact first; implement only if preview data is actually rendered in the alert list

## Testing

- **Issue 1:** Manual — navigate to a trade alert via `/alerts/<id>`, verify breadcrumbs appear, layout matches trade blotter style, `AlertSidePanel` still renders with decisions/status
- **Issue 2:** If implemented — call `GET /api/v1/alerts` with trade alerts in the DB, verify response includes preview data for trade alerts
