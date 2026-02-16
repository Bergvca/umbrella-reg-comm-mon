import { apiFetch } from "./client";
import type { AlertStats, AlertOut, AlertWithMessage, PaginatedResponse } from "@/lib/types";

export async function getAlertStats(): Promise<AlertStats> {
  return apiFetch<AlertStats>("/alerts/stats");
}

export interface AlertListParams {
  severity?: string;
  status?: string;
  rule_id?: string;
  offset?: number;
  limit?: number;
}

export async function getAlerts(
  params: AlertListParams = {},
): Promise<PaginatedResponse<AlertOut>> {
  const searchParams = new URLSearchParams();
  if (params.severity) searchParams.set("severity", params.severity);
  if (params.status) searchParams.set("status", params.status);
  if (params.rule_id) searchParams.set("rule_id", params.rule_id);
  searchParams.set("offset", String(params.offset ?? 0));
  searchParams.set("limit", String(params.limit ?? 50));
  return apiFetch<PaginatedResponse<AlertOut>>(`/alerts?${searchParams.toString()}`);
}

export async function getAlert(id: string): Promise<AlertWithMessage> {
  return apiFetch<AlertWithMessage>(`/alerts/${id}`);
}

export async function updateAlertStatus(
  id: string,
  status: string,
): Promise<AlertOut> {
  return apiFetch<AlertOut>(`/alerts/${id}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}
