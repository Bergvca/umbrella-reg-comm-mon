import { apiFetch } from "./client";
import type { GroupOut, GroupDetail, UserOut, PaginatedResponse } from "@/lib/types";

export async function getGroups(params: { offset?: number; limit?: number } = {}): Promise<PaginatedResponse<GroupDetail>> {
  const sp = new URLSearchParams();
  sp.set("offset", String(params.offset ?? 0));
  sp.set("limit", String(params.limit ?? 50));
  return apiFetch(`/groups?${sp.toString()}`);
}

export async function getGroup(id: string): Promise<GroupDetail> {
  return apiFetch(`/groups/${id}`);
}

export async function createGroup(body: { name: string; description?: string }): Promise<GroupOut> {
  return apiFetch("/groups", { method: "POST", body: JSON.stringify(body) });
}

export async function updateGroup(id: string, body: { name?: string; description?: string }): Promise<GroupOut> {
  return apiFetch(`/groups/${id}`, { method: "PATCH", body: JSON.stringify(body) });
}

export async function getGroupMembers(groupId: string): Promise<UserOut[]> {
  return apiFetch(`/groups/${groupId}/members`);
}

export async function assignRoleToGroup(groupId: string, roleId: string): Promise<void> {
  return apiFetch(`/groups/${groupId}/roles`, { method: "POST", body: JSON.stringify({ role_id: roleId }) });
}

export async function removeRoleFromGroup(groupId: string, roleId: string): Promise<void> {
  return apiFetch(`/groups/${groupId}/roles/${roleId}`, { method: "DELETE" });
}
