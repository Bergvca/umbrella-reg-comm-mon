import { apiFetch } from "./client";
export async function getPolicies(params = {}) {
    const sp = new URLSearchParams();
    if (params.risk_model_id)
        sp.set("risk_model_id", params.risk_model_id);
    if (params.is_active !== undefined)
        sp.set("is_active", String(params.is_active));
    sp.set("offset", String(params.offset ?? 0));
    sp.set("limit", String(params.limit ?? 50));
    return apiFetch(`/policies?${sp.toString()}`);
}
export async function getPolicy(id) {
    return apiFetch(`/policies/${id}`);
}
export async function createPolicy(body) {
    return apiFetch("/policies", { method: "POST", body: JSON.stringify(body) });
}
export async function updatePolicy(id, body) {
    return apiFetch(`/policies/${id}`, { method: "PATCH", body: JSON.stringify(body) });
}
export async function getRules(policyId, params = {}) {
    const sp = new URLSearchParams();
    sp.set("offset", String(params.offset ?? 0));
    sp.set("limit", String(params.limit ?? 50));
    return apiFetch(`/policies/${policyId}/rules?${sp.toString()}`);
}
export async function createRule(policyId, body) {
    return apiFetch(`/policies/${policyId}/rules`, { method: "POST", body: JSON.stringify(body) });
}
export async function updateRule(ruleId, body) {
    return apiFetch(`/rules/${ruleId}`, { method: "PATCH", body: JSON.stringify(body) });
}
export async function deleteRule(ruleId) {
    return apiFetch(`/rules/${ruleId}`, { method: "DELETE" });
}
export async function getGroupPolicies(policyId) {
    return apiFetch(`/policies/${policyId}/groups`);
}
export async function assignGroupPolicy(policyId, groupId) {
    return apiFetch(`/policies/${policyId}/groups`, { method: "POST", body: JSON.stringify({ group_id: groupId }) });
}
export async function removeGroupPolicy(policyId, groupId) {
    return apiFetch(`/policies/${policyId}/groups/${groupId}`, { method: "DELETE" });
}
