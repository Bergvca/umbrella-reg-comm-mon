import { apiFetch } from "./client";
import type { DecisionOut, DecisionStatusOut } from "@/lib/types";

export async function getDecisions(alertId: string): Promise<DecisionOut[]> {
  return apiFetch<DecisionOut[]>(`/alerts/${alertId}/decisions`);
}

export async function createDecision(
  alertId: string,
  body: { status_id: string; comment?: string },
): Promise<DecisionOut> {
  return apiFetch<DecisionOut>(`/alerts/${alertId}/decisions`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function getDecisionStatuses(): Promise<DecisionStatusOut[]> {
  return apiFetch<DecisionStatusOut[]>("/decision-statuses");
}
