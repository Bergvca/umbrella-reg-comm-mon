import { apiFetch } from "./client";
export async function getDefaultQuery() {
    return apiFetch("/alert-generation/default-query");
}
export async function createGenerationJob(body) {
    return apiFetch("/alert-generation/jobs", {
        method: "POST",
        body: JSON.stringify(body),
    });
}
export async function listGenerationJobs() {
    return apiFetch("/alert-generation/jobs");
}
export async function getGenerationJob(id) {
    return apiFetch(`/alert-generation/jobs/${id}`);
}
export async function syncRules() {
    return apiFetch("/alert-generation/sync-rules", { method: "POST" });
}
