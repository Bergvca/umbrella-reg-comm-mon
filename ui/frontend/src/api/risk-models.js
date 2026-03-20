import { apiFetch } from "./client";
export async function getRiskModels(params = {}) {
    const sp = new URLSearchParams();
    if (params.is_active !== undefined)
        sp.set("is_active", String(params.is_active));
    sp.set("offset", String(params.offset ?? 0));
    sp.set("limit", String(params.limit ?? 50));
    return apiFetch(`/risk-models?${sp.toString()}`);
}
export async function getRiskModel(id) {
    return apiFetch(`/risk-models/${id}`);
}
export async function createRiskModel(body) {
    return apiFetch("/risk-models", { method: "POST", body: JSON.stringify(body) });
}
export async function updateRiskModel(id, body) {
    return apiFetch(`/risk-models/${id}`, { method: "PATCH", body: JSON.stringify(body) });
}
