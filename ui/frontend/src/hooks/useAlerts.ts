import { useQuery } from "@tanstack/react-query";
import { getAlertStats } from "@/api/alerts";

export function useAlertStats() {
  return useQuery({
    queryKey: ["alerts", "stats"],
    queryFn: getAlertStats,
    refetchInterval: 60_000, // auto-refresh every 60 seconds
  });
}
