import { apiFetch } from "./client";
export async function getEntities(params = {}) {
    const sp = new URLSearchParams();
    if (params.entity_type)
        sp.set("entity_type", params.entity_type);
    if (params.search)
        sp.set("search", params.search);
    if (params.attr_key)
        sp.set("attr_key", params.attr_key);
    if (params.attr_value)
        sp.set("attr_value", params.attr_value);
    sp.set("offset", String(params.offset ?? 0));
    sp.set("limit", String(params.limit ?? 50));
    return apiFetch(`/entities?${sp.toString()}`);
}
export async function getEntity(id) {
    return apiFetch(`/entities/${id}`);
}
export async function createEntity(body) {
    return apiFetch("/entities", {
        method: "POST",
        body: JSON.stringify(body),
    });
}
export async function updateEntity(id, body) {
    return apiFetch(`/entities/${id}`, {
        method: "PATCH",
        body: JSON.stringify(body),
    });
}
export async function deleteEntity(id) {
    return apiFetch(`/entities/${id}`, { method: "DELETE" });
}
export async function addHandle(entityId, body) {
    return apiFetch(`/entities/${entityId}/handles`, {
        method: "POST",
        body: JSON.stringify(body),
    });
}
export async function removeHandle(entityId, handleId) {
    return apiFetch(`/entities/${entityId}/handles/${handleId}`, {
        method: "DELETE",
    });
}
export async function addAttribute(entityId, body) {
    return apiFetch(`/entities/${entityId}/attributes`, {
        method: "POST",
        body: JSON.stringify(body),
    });
}
export async function removeAttribute(entityId, attrId) {
    return apiFetch(`/entities/${entityId}/attributes/${attrId}`, {
        method: "DELETE",
    });
}
export async function batchUploadJson(items) {
    return apiFetch("/entities/batch", {
        method: "POST",
        body: JSON.stringify(items),
    });
}
export async function getEntityMessages(entityId, params = {}) {
    const sp = new URLSearchParams();
    sp.set("offset", String(params.offset ?? 0));
    sp.set("limit", String(params.limit ?? 20));
    return apiFetch(`/entities/${entityId}/messages?${sp.toString()}`);
}
export async function getEntityAlerts(entityId) {
    return apiFetch(`/entities/${entityId}/alerts`);
}
export async function batchUploadCsv(file) {
    const formData = new FormData();
    formData.append("file", file);
    return apiFetch("/entities/batch/csv", {
        method: "POST",
        body: formData,
        headers: {}, // let browser set Content-Type with boundary
    });
}
