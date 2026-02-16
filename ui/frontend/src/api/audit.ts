import { apiFetch } from "./client";
import type { AuditLogEntry, PaginatedResponse } from "@/lib/types";

export interface AuditLogParams {
  actor_id?: string;
  alert_id?: string;
  object_type?: string;
  date_from?: string;
  date_to?: string;
  offset?: number;
  limit?: number;
}

export async function getAuditLog(params: AuditLogParams = {}): Promise<PaginatedResponse<AuditLogEntry>> {
  const sp = new URLSearchParams();
  if (params.actor_id) sp.set("actor_id", params.actor_id);
  if (params.alert_id) sp.set("alert_id", params.alert_id);
  if (params.object_type) sp.set("object_type", params.object_type);
  if (params.date_from) sp.set("date_from", params.date_from);
  if (params.date_to) sp.set("date_to", params.date_to);
  sp.set("offset", String(params.offset ?? 0));
  sp.set("limit", String(params.limit ?? 50));
  return apiFetch(`/audit-log?${sp.toString()}`);
}
