import { apiFetch } from "./client";

export interface TradeParticipant {
  id: string;
  name: string;
  role: string;
  entity_id?: string;
  entity_name?: string;
}

export interface TradeMetadata {
  ticker?: string;
  side?: string;
  quantity?: number;
  price?: number;
  notional?: number;
  currency?: string;
  order_type?: string;
  venue?: string;
  execution_id?: string;
  asset_class?: string;
  account_id?: string;
  settlement_date?: string;
  order_id?: string;
}

export interface Trade {
  message_id: string;
  channel: string;
  direction?: string;
  timestamp: string;
  participants: TradeParticipant[];
  body_text?: string;
  metadata: TradeMetadata;
}

export interface TradeHit {
  trade: Trade;
  index: string;
  score: number | null;
}

export interface TradeSearchResponse {
  hits: TradeHit[];
  total: number;
  offset: number;
  limit: number;
}

export interface TradeAggBucket {
  key: string;
  doc_count: number;
  total_quantity?: number;
  total_notional?: number;
}

export interface TradeStatsResponse {
  by_ticker: TradeAggBucket[];
  by_side: TradeAggBucket[];
  by_venue: TradeAggBucket[];
  total_trades: number;
}

export interface TradeSearchParams {
  q?: string;
  ticker?: string;
  side?: string;
  participant?: string;
  venue?: string;
  account_id?: string;
  quantity_min?: number;
  quantity_max?: number;
  price_min?: number;
  price_max?: number;
  date_from?: string;
  date_to?: string;
  offset?: number;
  limit?: number;
}

export async function searchTrades(
  params: TradeSearchParams = {},
): Promise<TradeSearchResponse> {
  const sp = new URLSearchParams();
  if (params.q) sp.set("q", params.q);
  if (params.ticker) sp.set("ticker", params.ticker);
  if (params.side) sp.set("side", params.side);
  if (params.participant) sp.set("participant", params.participant);
  if (params.venue) sp.set("venue", params.venue);
  if (params.account_id) sp.set("account_id", params.account_id);
  if (params.quantity_min != null) sp.set("quantity_min", String(params.quantity_min));
  if (params.quantity_max != null) sp.set("quantity_max", String(params.quantity_max));
  if (params.price_min != null) sp.set("price_min", String(params.price_min));
  if (params.price_max != null) sp.set("price_max", String(params.price_max));
  if (params.date_from) sp.set("date_from", params.date_from);
  if (params.date_to) sp.set("date_to", params.date_to);
  sp.set("offset", String(params.offset ?? 0));
  sp.set("limit", String(params.limit ?? 20));
  return apiFetch(`/trades/search?${sp.toString()}`);
}

export async function getTradeStats(params: {
  participant?: string;
  date_from?: string;
  date_to?: string;
} = {}): Promise<TradeStatsResponse> {
  const sp = new URLSearchParams();
  if (params.participant) sp.set("participant", params.participant);
  if (params.date_from) sp.set("date_from", params.date_from);
  if (params.date_to) sp.set("date_to", params.date_to);
  return apiFetch(`/trades/stats?${sp.toString()}`);
}

export async function getTrade(
  index: string,
  docId: string,
): Promise<Trade> {
  return apiFetch(`/trades/${index}/${docId}`);
}
