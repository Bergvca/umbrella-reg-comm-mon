import { apiFetch } from "./client";
export async function getAlertStats() {
    return apiFetch("/alerts/stats");
}
