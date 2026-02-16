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
export async function getBatchItems(queueId, batchId) {
    return apiFetch(`/queues/${queueId}/batches/${batchId}/items`);
}
export async function getMyQueue() {
    return apiFetch("/my-queue");
}
