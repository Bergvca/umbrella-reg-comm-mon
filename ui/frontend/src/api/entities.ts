import { apiFetch } from "./client";
import type {
  AlertOut,
  EntityOut,
  ESMessageHit,
  HandleOut,
  AttributeOut,
  BatchUploadResult,
  PaginatedResponse,
} from "@/lib/types";

export interface EntityListParams {
  entity_type?: string;
  search?: string;
  attr_key?: string;
  attr_value?: string;
  offset?: number;
  limit?: number;
}

export async function getEntities(
  params: EntityListParams = {},
): Promise<PaginatedResponse<EntityOut>> {
  const sp = new URLSearchParams();
  if (params.entity_type) sp.set("entity_type", params.entity_type);
  if (params.search) sp.set("search", params.search);
  if (params.attr_key) sp.set("attr_key", params.attr_key);
  if (params.attr_value) sp.set("attr_value", params.attr_value);
  sp.set("offset", String(params.offset ?? 0));
  sp.set("limit", String(params.limit ?? 50));
  return apiFetch<PaginatedResponse<EntityOut>>(`/entities?${sp.toString()}`);
}

export async function getEntity(id: string): Promise<EntityOut> {
  return apiFetch<EntityOut>(`/entities/${id}`);
}

export interface EntityCreateBody {
  display_name: string;
  entity_type: string;
  handles?: { handle_type: string; handle_value: string; is_primary?: boolean }[];
  attributes?: { attr_key: string; attr_value: string }[];
}

export async function createEntity(body: EntityCreateBody): Promise<EntityOut> {
  return apiFetch<EntityOut>("/entities", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function updateEntity(
  id: string,
  body: { display_name?: string; entity_type?: string },
): Promise<EntityOut> {
  return apiFetch<EntityOut>(`/entities/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export async function deleteEntity(id: string): Promise<void> {
  return apiFetch<void>(`/entities/${id}`, { method: "DELETE" });
}

export async function addHandle(
  entityId: string,
  body: { handle_type: string; handle_value: string; is_primary?: boolean },
): Promise<HandleOut> {
  return apiFetch<HandleOut>(`/entities/${entityId}/handles`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function removeHandle(entityId: string, handleId: string): Promise<void> {
  return apiFetch<void>(`/entities/${entityId}/handles/${handleId}`, {
    method: "DELETE",
  });
}

export async function addAttribute(
  entityId: string,
  body: { attr_key: string; attr_value: string; valid_from?: string; valid_to?: string },
): Promise<AttributeOut> {
  return apiFetch<AttributeOut>(`/entities/${entityId}/attributes`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function removeAttribute(entityId: string, attrId: string): Promise<void> {
  return apiFetch<void>(`/entities/${entityId}/attributes/${attrId}`, {
    method: "DELETE",
  });
}

export async function batchUploadJson(
  items: EntityCreateBody[],
): Promise<BatchUploadResult> {
  return apiFetch<BatchUploadResult>("/entities/batch", {
    method: "POST",
    body: JSON.stringify(items),
  });
}

export async function getEntityMessages(
  entityId: string,
  params: { offset?: number; limit?: number } = {},
): Promise<PaginatedResponse<ESMessageHit>> {
  const sp = new URLSearchParams();
  sp.set("offset", String(params.offset ?? 0));
  sp.set("limit", String(params.limit ?? 20));
  return apiFetch<PaginatedResponse<ESMessageHit>>(`/entities/${entityId}/messages?${sp.toString()}`);
}

export async function getEntityAlerts(entityId: string): Promise<AlertOut[]> {
  return apiFetch<AlertOut[]>(`/entities/${entityId}/alerts`);
}

export async function batchUploadCsv(file: File): Promise<BatchUploadResult> {
  const formData = new FormData();
  formData.append("file", file);
  return apiFetch<BatchUploadResult>("/entities/batch/csv", {
    method: "POST",
    body: formData,
    headers: {}, // let browser set Content-Type with boundary
  });
}
