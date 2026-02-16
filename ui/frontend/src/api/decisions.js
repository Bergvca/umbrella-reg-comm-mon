import { apiFetch } from "./client";
export async function getDecisions(alertId) {
    return apiFetch(`/alerts/${alertId}/decisions`);
}
export async function createDecision(alertId, body) {
    return apiFetch(`/alerts/${alertId}/decisions`, {
        method: "POST",
        body: JSON.stringify(body),
    });
}
export async function getDecisionStatuses() {
    return apiFetch("/decision-statuses");
}
