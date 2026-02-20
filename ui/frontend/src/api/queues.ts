import { apiFetch } from "./client";
import type { QueueOut, QueueDetail, BatchOut, PaginatedResponse, QueueItemOut, AlertOut } from "@/lib/types";

export async function getQueues(
  params: { offset?: number; limit?: number } = {},
): Promise<PaginatedResponse<QueueOut>> {
  const sp = new URLSearchParams();
  sp.set("offset", String(params.offset ?? 0));
  sp.set("limit", String(params.limit ?? 50));
  return apiFetch(`/queues?${sp.toString()}`);
}

export async function getQueue(id: string): Promise<QueueDetail> {
  return apiFetch(`/queues/${id}`);
}

export async function getBatches(queueId: string): Promise<BatchOut[]> {
  return apiFetch(`/queues/${queueId}/batches`);
}

export async function getBatchItems(
  queueId: string,
  batchId: string,
): Promise<QueueItemOut[]> {
  return apiFetch(`/queues/${queueId}/batches/${batchId}/items`);
}

export async function getMyQueue(): Promise<BatchOut[]> {
  return apiFetch("/my-queue");
}

export async function createQueue(body: { name: string; description?: string; policy_id: string }): Promise<QueueOut> {
  return apiFetch("/queues", { method: "POST", body: JSON.stringify(body) });
}

export async function createBatch(queueId: string, body: { name?: string }): Promise<BatchOut> {
  return apiFetch(`/queues/${queueId}/batches`, { method: "POST", body: JSON.stringify(body) });
}

export async function generateBatches(queueId: string): Promise<BatchOut[]> {
  return apiFetch(`/queues/${queueId}/generate-batches`, { method: "POST" });
}

export async function getBatchAlerts(queueId: string, batchId: string): Promise<AlertOut[]> {
  return apiFetch(`/queues/${queueId}/batches/${batchId}/alerts`);
}

export async function updateBatch(queueId: string, batchId: string, body: { assigned_to?: string; status?: string }): Promise<BatchOut> {
  return apiFetch(`/queues/${queueId}/batches/${batchId}`, { method: "PATCH", body: JSON.stringify(body) });
}

export async function addItemToBatch(queueId: string, batchId: string, body: { alert_id: string; position: number }): Promise<QueueItemOut> {
  return apiFetch(`/queues/${queueId}/batches/${batchId}/items`, { method: "POST", body: JSON.stringify(body) });
}
