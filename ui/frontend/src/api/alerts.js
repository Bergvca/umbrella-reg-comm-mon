import { apiFetch } from "./client";
export async function getAlertStats() {
    return apiFetch("/alerts/stats");
}
export async function getAlerts(params = {}) {
    const searchParams = new URLSearchParams();
    if (params.severity)
        searchParams.set("severity", params.severity);
    if (params.status)
        searchParams.set("status", params.status);
    if (params.rule_id)
        searchParams.set("rule_id", params.rule_id);
    searchParams.set("offset", String(params.offset ?? 0));
    searchParams.set("limit", String(params.limit ?? 50));
    return apiFetch(`/alerts?${searchParams.toString()}`);
}
export async function getAlert(id) {
    return apiFetch(`/alerts/${id}`);
}
export async function updateAlertStatus(id, status) {
    return apiFetch(`/alerts/${id}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
    });
}
