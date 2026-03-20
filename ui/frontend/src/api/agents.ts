import { apiFetch } from "./client";
import type {
  AgentOut,
  ModelOut,
  ToolOut,
  RunOut,
  PaginatedResponse,
} from "@/lib/types";

export interface AgentListParams {
  is_builtin?: boolean;
  is_active?: boolean;
  offset?: number;
  limit?: number;
}

export interface AgentCreateBody {
  name: string;
  description?: string;
  model_id: string;
  system_prompt: string;
  temperature?: number;
  max_iterations?: number;
  output_schema?: Record<string, unknown> | null;
  tool_ids?: string[];
  data_sources?: { source_type: string; source_identifier: string }[];
}

export interface AgentUpdateBody {
  name?: string;
  description?: string;
  model_id?: string;
  system_prompt?: string;
  temperature?: number;
  max_iterations?: number;
  output_schema?: Record<string, unknown> | null;
  is_active?: boolean;
  tool_ids?: string[];
  data_sources?: { source_type: string; source_identifier: string }[];
}

export interface RunListParams {
  agent_id?: string;
  status?: string;
  offset?: number;
  limit?: number;
}

export async function getAgents(
  params: AgentListParams = {},
): Promise<PaginatedResponse<AgentOut>> {
  const sp = new URLSearchParams();
  if (params.is_builtin != null) sp.set("is_builtin", String(params.is_builtin));
  if (params.is_active != null) sp.set("is_active", String(params.is_active));
  sp.set("offset", String(params.offset ?? 0));
  sp.set("limit", String(params.limit ?? 50));
  return apiFetch<PaginatedResponse<AgentOut>>(`/agents?${sp.toString()}`);
}

export async function getAgent(id: string): Promise<AgentOut> {
  return apiFetch<AgentOut>(`/agents/${id}`);
}

export async function createAgent(body: AgentCreateBody): Promise<AgentOut> {
  return apiFetch<AgentOut>("/agents", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function updateAgent(id: string, body: AgentUpdateBody): Promise<AgentOut> {
  return apiFetch<AgentOut>(`/agents/${id}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export async function deleteAgent(id: string): Promise<void> {
  return apiFetch<void>(`/agents/${id}`, { method: "DELETE" });
}

export async function cloneAgent(id: string): Promise<AgentOut> {
  return apiFetch<AgentOut>(`/agents/${id}/clone`, { method: "POST" });
}

export async function getAgentModels(
  params: { offset?: number; limit?: number } = {},
): Promise<PaginatedResponse<ModelOut>> {
  const sp = new URLSearchParams();
  sp.set("offset", String(params.offset ?? 0));
  sp.set("limit", String(params.limit ?? 100));
  return apiFetch<PaginatedResponse<ModelOut>>(`/agent-models?${sp.toString()}`);
}

export async function getAgentTools(
  params: { category?: string; offset?: number; limit?: number } = {},
): Promise<PaginatedResponse<ToolOut>> {
  const sp = new URLSearchParams();
  if (params.category) sp.set("category", params.category);
  sp.set("offset", String(params.offset ?? 0));
  sp.set("limit", String(params.limit ?? 100));
  return apiFetch<PaginatedResponse<ToolOut>>(`/agent-tools?${sp.toString()}`);
}

export async function executeAgent(body: { agent_id: string; input: string }): Promise<RunOut> {
  return apiFetch<RunOut>("/agent-runs", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function getAgentRuns(
  params: RunListParams = {},
): Promise<PaginatedResponse<RunOut>> {
  const sp = new URLSearchParams();
  if (params.agent_id) sp.set("agent_id", params.agent_id);
  if (params.status) sp.set("status", params.status);
  sp.set("offset", String(params.offset ?? 0));
  sp.set("limit", String(params.limit ?? 20));
  return apiFetch<PaginatedResponse<RunOut>>(`/agent-runs?${sp.toString()}`);
}

export async function getAgentRun(runId: string): Promise<RunOut> {
  return apiFetch<RunOut>(`/agent-runs/${runId}`);
}

// -- Data source options --

export interface DataSourceOptions {
  elasticsearch_indices: string[];
  postgresql_tables: string[];
}

export async function getDataSourceOptions(): Promise<DataSourceOptions> {
  return apiFetch<DataSourceOptions>("/agent-data-sources/options");
}

// -- Streaming execution --

export async function executeAgentStream(body: {
  agent_id: string;
  input: string;
}): Promise<{ run_id: string; status: string }> {
  return apiFetch("/agent-runs/stream", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function agentRunStreamUrl(runId: string): string {
  return `/api/v1/agent-runs/${runId}/stream`;
}

export async function cancelAgentRun(runId: string): Promise<void> {
  return apiFetch(`/agent-runs/${runId}/cancel`, { method: "POST" });
}
