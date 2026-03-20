import { apiFetch } from "./client";
export async function getAgents(params = {}) {
    const sp = new URLSearchParams();
    if (params.is_builtin != null)
        sp.set("is_builtin", String(params.is_builtin));
    if (params.is_active != null)
        sp.set("is_active", String(params.is_active));
    sp.set("offset", String(params.offset ?? 0));
    sp.set("limit", String(params.limit ?? 50));
    return apiFetch(`/agents?${sp.toString()}`);
}
export async function getAgent(id) {
    return apiFetch(`/agents/${id}`);
}
export async function createAgent(body) {
    return apiFetch("/agents", {
        method: "POST",
        body: JSON.stringify(body),
    });
}
export async function updateAgent(id, body) {
    return apiFetch(`/agents/${id}`, {
        method: "PUT",
        body: JSON.stringify(body),
    });
}
export async function deleteAgent(id) {
    return apiFetch(`/agents/${id}`, { method: "DELETE" });
}
export async function cloneAgent(id) {
    return apiFetch(`/agents/${id}/clone`, { method: "POST" });
}
export async function getAgentModels(params = {}) {
    const sp = new URLSearchParams();
    sp.set("offset", String(params.offset ?? 0));
    sp.set("limit", String(params.limit ?? 100));
    return apiFetch(`/agent-models?${sp.toString()}`);
}
export async function getAgentTools(params = {}) {
    const sp = new URLSearchParams();
    if (params.category)
        sp.set("category", params.category);
    sp.set("offset", String(params.offset ?? 0));
    sp.set("limit", String(params.limit ?? 100));
    return apiFetch(`/agent-tools?${sp.toString()}`);
}
export async function executeAgent(body) {
    return apiFetch("/agent-runs", {
        method: "POST",
        body: JSON.stringify(body),
    });
}
export async function getAgentRuns(params = {}) {
    const sp = new URLSearchParams();
    if (params.agent_id)
        sp.set("agent_id", params.agent_id);
    if (params.status)
        sp.set("status", params.status);
    sp.set("offset", String(params.offset ?? 0));
    sp.set("limit", String(params.limit ?? 20));
    return apiFetch(`/agent-runs?${sp.toString()}`);
}
export async function getAgentRun(runId) {
    return apiFetch(`/agent-runs/${runId}`);
}
export async function getDataSourceOptions() {
    return apiFetch("/agent-data-sources/options");
}
// -- Streaming execution --
export async function executeAgentStream(body) {
    return apiFetch("/agent-runs/stream", {
        method: "POST",
        body: JSON.stringify(body),
    });
}
export function agentRunStreamUrl(runId) {
    return `/api/v1/agent-runs/${runId}/stream`;
}
export async function cancelAgentRun(runId) {
    return apiFetch(`/agent-runs/${runId}/cancel`, { method: "POST" });
}
