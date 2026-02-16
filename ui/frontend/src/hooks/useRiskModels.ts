import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import * as api from "@/api/risk-models";

export function useRiskModels(params: { is_active?: boolean; offset?: number; limit?: number } = {}) {
  return useQuery({
    queryKey: ["risk-models", "list", params],
    queryFn: () => api.getRiskModels(params),
  });
}

export function useRiskModel(id: string) {
  return useQuery({
    queryKey: ["risk-models", id],
    queryFn: () => api.getRiskModel(id),
    enabled: !!id,
  });
}

export function useCreateRiskModel() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.createRiskModel,
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ["risk-models"] }); },
  });
}

export function useUpdateRiskModel() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: { id: string; name?: string; description?: string; is_active?: boolean }) =>
      api.updateRiskModel(id, body),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ["risk-models"] }); },
  });
}
