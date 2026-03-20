import { apiFetch } from "./client";
export async function searchTrades(params = {}) {
    const sp = new URLSearchParams();
    if (params.q)
        sp.set("q", params.q);
    if (params.ticker)
        sp.set("ticker", params.ticker);
    if (params.side)
        sp.set("side", params.side);
    if (params.participant)
        sp.set("participant", params.participant);
    if (params.venue)
        sp.set("venue", params.venue);
    if (params.account_id)
        sp.set("account_id", params.account_id);
    if (params.quantity_min != null)
        sp.set("quantity_min", String(params.quantity_min));
    if (params.quantity_max != null)
        sp.set("quantity_max", String(params.quantity_max));
    if (params.price_min != null)
        sp.set("price_min", String(params.price_min));
    if (params.price_max != null)
        sp.set("price_max", String(params.price_max));
    if (params.date_from)
        sp.set("date_from", params.date_from);
    if (params.date_to)
        sp.set("date_to", params.date_to);
    sp.set("offset", String(params.offset ?? 0));
    sp.set("limit", String(params.limit ?? 20));
    return apiFetch(`/trades/search?${sp.toString()}`);
}
export async function getTradeStats(params = {}) {
    const sp = new URLSearchParams();
    if (params.participant)
        sp.set("participant", params.participant);
    if (params.date_from)
        sp.set("date_from", params.date_from);
    if (params.date_to)
        sp.set("date_to", params.date_to);
    return apiFetch(`/trades/stats?${sp.toString()}`);
}
export async function getTrade(index, docId) {
    return apiFetch(`/trades/${index}/${docId}`);
}
