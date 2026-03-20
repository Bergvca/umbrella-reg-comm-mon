import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "@/api/alert-generation";
import type { GenerationJobCreate, GenerationJobOut } from "@/lib/types";

export function useDefaultQuery() {
  return useQuery({
    queryKey: ["generation-jobs", "default-query"],
    queryFn: api.getDefaultQuery,
  });
}

export function useGenerationJobs() {
  return useQuery({
    queryKey: ["generation-jobs", "list"],
    queryFn: api.listGenerationJobs,
  });
}

export function useGenerationJob(id: string | null) {
  return useQuery({
    queryKey: ["generation-jobs", id],
    queryFn: () => api.getGenerationJob(id!),
    enabled: !!id,
    refetchInterval: (query) => {
      const status = (query.state.data as GenerationJobOut | undefined)?.status;
      return !status || status === "pending" || status === "running" ? 2000 : false;
    },
  });
}

export function useCreateGenerationJob() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: GenerationJobCreate) => api.createGenerationJob(body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["generation-jobs"] });
    },
  });
}
