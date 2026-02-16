import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getAlertStats,
  getAlerts,
  getAlert,
  updateAlertStatus,
} from "@/api/alerts";
import type { AlertListParams } from "@/api/alerts";

export function useAlertStats() {
  return useQuery({
    queryKey: ["alerts", "stats"],
    queryFn: getAlertStats,
    refetchInterval: 60_000,
  });
}

export function useAlerts(params: AlertListParams) {
  return useQuery({
    queryKey: ["alerts", "list", params],
    queryFn: () => getAlerts(params),
  });
}

export function useAlert(id: string) {
  return useQuery({
    queryKey: ["alerts", id],
    queryFn: () => getAlert(id),
    enabled: !!id,
  });
}

export function useUpdateAlertStatus() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      updateAlertStatus(id, status),
    onSuccess: (_data, { id }) => {
      void queryClient.invalidateQueries({ queryKey: ["alerts", id] });
      void queryClient.invalidateQueries({ queryKey: ["alerts", "list"] });
      void queryClient.invalidateQueries({ queryKey: ["alerts", "stats"] });
    },
  });
}
