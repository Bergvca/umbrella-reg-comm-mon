import { apiFetch } from "./client";
export async function getQueues(params = {}) {
    const sp = new URLSearchParams();
    sp.set("offset", String(params.offset ?? 0));
    sp.set("limit", String(params.limit ?? 50));
    return apiFetch(`/queues?${sp.toString()}`);
}
export async function getQueue(id) {
    return apiFetch(`/queues/${id}`);
}
export async function getBatches(queueId) {
    return apiFetch(`/queues/${queueId}/batches`);
}
export async function getBatchItems(queueId, batchId) {
    return apiFetch(`/queues/${queueId}/batches/${batchId}/items`);
}
export async function getMyQueue() {
    return apiFetch("/my-queue");
}
export async function createQueue(body) {
    return apiFetch("/queues", { method: "POST", body: JSON.stringify(body) });
}
export async function createBatch(queueId, body) {
    return apiFetch(`/queues/${queueId}/batches`, { method: "POST", body: JSON.stringify(body) });
}
export async function generateBatches(queueId) {
    return apiFetch(`/queues/${queueId}/generate-batches`, { method: "POST" });
}
export async function getBatchAlerts(queueId, batchId) {
    return apiFetch(`/queues/${queueId}/batches/${batchId}/alerts`);
}
export async function updateBatch(queueId, batchId, body) {
    return apiFetch(`/queues/${queueId}/batches/${batchId}`, { method: "PATCH", body: JSON.stringify(body) });
}
export async function addItemToBatch(queueId, batchId, body) {
    return apiFetch(`/queues/${queueId}/batches/${batchId}/items`, { method: "POST", body: JSON.stringify(body) });
}
