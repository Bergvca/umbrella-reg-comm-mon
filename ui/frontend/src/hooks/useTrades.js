import { useQuery } from "@tanstack/react-query";
import { searchTrades, getTrade, getTradeStats } from "@/api/trades";
export function useTradeSearch(params) {
    return useQuery({
        queryKey: ["trades", "search", params],
        queryFn: () => searchTrades(params),
        enabled: !!(params.q ||
            params.ticker ||
            params.side ||
            params.participant ||
            params.date_from),
    });
}
export function useTradeStats(params = {}) {
    return useQuery({
        queryKey: ["trades", "stats", params],
        queryFn: () => getTradeStats(params),
    });
}
export function useTrade(index, docId) {
    return useQuery({
        queryKey: ["trades", index, docId],
        queryFn: () => getTrade(index, docId),
        enabled: !!index && !!docId,
    });
}
