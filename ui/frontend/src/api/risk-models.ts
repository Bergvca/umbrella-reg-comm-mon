import { apiFetch } from "./client";
import type { RiskModelDetail, RiskModelOut, PaginatedResponse } from "@/lib/types";

export async function getRiskModels(params: { is_active?: boolean; offset?: number; limit?: number } = {}): Promise<PaginatedResponse<RiskModelDetail>> {
  const sp = new URLSearchParams();
  if (params.is_active !== undefined) sp.set("is_active", String(params.is_active));
  sp.set("offset", String(params.offset ?? 0));
  sp.set("limit", String(params.limit ?? 50));
  return apiFetch(`/risk-models?${sp.toString()}`);
}

export async function getRiskModel(id: string): Promise<RiskModelDetail> {
  return apiFetch(`/risk-models/${id}`);
}

export async function createRiskModel(body: { name: string; description?: string }): Promise<RiskModelOut> {
  return apiFetch("/risk-models", { method: "POST", body: JSON.stringify(body) });
}

export async function updateRiskModel(id: string, body: { name?: string; description?: string; is_active?: boolean }): Promise<RiskModelOut> {
  return apiFetch(`/risk-models/${id}`, { method: "PATCH", body: JSON.stringify(body) });
}
