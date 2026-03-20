import { apiFetch } from "./client";
export async function getGroups(params = {}) {
    const sp = new URLSearchParams();
    sp.set("offset", String(params.offset ?? 0));
    sp.set("limit", String(params.limit ?? 50));
    return apiFetch(`/groups?${sp.toString()}`);
}
export async function getGroup(id) {
    return apiFetch(`/groups/${id}`);
}
export async function createGroup(body) {
    return apiFetch("/groups", { method: "POST", body: JSON.stringify(body) });
}
export async function updateGroup(id, body) {
    return apiFetch(`/groups/${id}`, { method: "PATCH", body: JSON.stringify(body) });
}
export async function getGroupMembers(groupId) {
    return apiFetch(`/groups/${groupId}/members`);
}
export async function assignRoleToGroup(groupId, roleId) {
    return apiFetch(`/groups/${groupId}/roles`, { method: "POST", body: JSON.stringify({ role_id: roleId }) });
}
export async function removeRoleFromGroup(groupId, roleId) {
    return apiFetch(`/groups/${groupId}/roles/${roleId}`, { method: "DELETE" });
}
