import { apiFetch } from "./client";
export async function getAuditLog(params = {}) {
    const sp = new URLSearchParams();
    if (params.actor_id)
        sp.set("actor_id", params.actor_id);
    if (params.alert_id)
        sp.set("alert_id", params.alert_id);
    if (params.object_type)
        sp.set("object_type", params.object_type);
    if (params.date_from)
        sp.set("date_from", params.date_from);
    if (params.date_to)
        sp.set("date_to", params.date_to);
    sp.set("offset", String(params.offset ?? 0));
    sp.set("limit", String(params.limit ?? 50));
    return apiFetch(`/audit-log?${sp.toString()}`);
}
