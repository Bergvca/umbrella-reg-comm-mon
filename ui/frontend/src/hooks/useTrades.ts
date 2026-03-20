import { useQuery } from "@tanstack/react-query";
import { searchTrades, getTrade, getTradeStats } from "@/api/trades";
import type { TradeSearchParams } from "@/api/trades";

export function useTradeSearch(params: TradeSearchParams) {
  return useQuery({
    queryKey: ["trades", "search", params],
    queryFn: () => searchTrades(params),
    enabled: !!(
      params.q ||
      params.ticker ||
      params.side ||
      params.participant ||
      params.date_from
    ),
  });
}

export function useTradeStats(params: {
  participant?: string;
  date_from?: string;
  date_to?: string;
} = {}) {
  return useQuery({
    queryKey: ["trades", "stats", params],
    queryFn: () => getTradeStats(params),
  });
}

export function useTrade(index: string, docId: string) {
  return useQuery({
    queryKey: ["trades", index, docId],
    queryFn: () => getTrade(index, docId),
    enabled: !!index && !!docId,
  });
}
