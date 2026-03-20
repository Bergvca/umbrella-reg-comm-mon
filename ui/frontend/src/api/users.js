import { apiFetch } from "./client";
export async function getUsers(params = {}) {
    const sp = new URLSearchParams();
    sp.set("offset", String(params.offset ?? 0));
    sp.set("limit", String(params.limit ?? 50));
    return apiFetch(`/users?${sp.toString()}`);
}
export async function getUser(id) {
    return apiFetch(`/users/${id}`);
}
export async function createUser(body) {
    return apiFetch("/users", { method: "POST", body: JSON.stringify(body) });
}
export async function updateUser(id, body) {
    return apiFetch(`/users/${id}`, { method: "PATCH", body: JSON.stringify(body) });
}
export async function getUserGroups(userId) {
    return apiFetch(`/users/${userId}/groups`);
}
export async function addUserToGroup(userId, groupId) {
    return apiFetch(`/users/${userId}/groups`, { method: "POST", body: JSON.stringify({ group_id: groupId }) });
}
export async function removeUserFromGroup(userId, groupId) {
    return apiFetch(`/users/${userId}/groups/${groupId}`, { method: "DELETE" });
}
