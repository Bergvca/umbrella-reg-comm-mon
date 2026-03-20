import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getAgents,
  getAgent,
  createAgent,
  updateAgent,
  deleteAgent,
  cloneAgent,
  getAgentModels,
  getAgentTools,
  getDataSourceOptions,
  executeAgent,
  getAgentRuns,
  getAgentRun,
} from "@/api/agents";
import type { AgentListParams, AgentCreateBody, AgentUpdateBody, RunListParams } from "@/api/agents";

export function useAgents(params: AgentListParams = {}) {
  return useQuery({
    queryKey: ["agents", "list", params],
    queryFn: () => getAgents(params),
  });
}

export function useAgent(id: string) {
  return useQuery({
    queryKey: ["agents", id],
    queryFn: () => getAgent(id),
    enabled: !!id,
  });
}

export function useAgentModels() {
  return useQuery({
    queryKey: ["agent-models", "list"],
    queryFn: () => getAgentModels({ limit: 100 }),
  });
}

export function useAgentTools() {
  return useQuery({
    queryKey: ["agent-tools", "list"],
    queryFn: () => getAgentTools({ limit: 100 }),
  });
}

export function useDataSourceOptions() {
  return useQuery({
    queryKey: ["agent-data-sources", "options"],
    queryFn: () => getDataSourceOptions(),
  });
}

export function useAgentRuns(params: RunListParams = {}) {
  return useQuery({
    queryKey: ["agent-runs", "list", params],
    queryFn: () => getAgentRuns(params),
    enabled: !!params.agent_id || params.agent_id === undefined,
  });
}

export function useAgentRun(runId: string) {
  return useQuery({
    queryKey: ["agent-runs", runId],
    queryFn: () => getAgentRun(runId),
    enabled: !!runId,
  });
}

export function useCreateAgent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: AgentCreateBody) => createAgent(body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["agents", "list"] });
    },
  });
}

export function useUpdateAgent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: AgentUpdateBody }) =>
      updateAgent(id, body),
    onSuccess: (_data, { id }) => {
      void qc.invalidateQueries({ queryKey: ["agents", id] });
      void qc.invalidateQueries({ queryKey: ["agents", "list"] });
    },
  });
}

export function useDeleteAgent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteAgent(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["agents", "list"] });
    },
  });
}

export function useCloneAgent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => cloneAgent(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["agents", "list"] });
    },
  });
}

export function useExecuteAgent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { agent_id: string; input: string }) => executeAgent(body),
    onSuccess: (_data, { agent_id }) => {
      void qc.invalidateQueries({ queryKey: ["agent-runs", "list", { agent_id }] });
    },
  });
}
