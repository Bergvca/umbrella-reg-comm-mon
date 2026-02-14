import { apiFetch } from "./client";
import type { AlertStats } from "@/lib/types";

export async function getAlertStats(): Promise<AlertStats> {
  return apiFetch<AlertStats>("/alerts/stats");
}
