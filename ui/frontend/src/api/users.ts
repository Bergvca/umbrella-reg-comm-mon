import { apiFetch } from "./client";
import type { UserOut, UserWithRoles, GroupOut, PaginatedResponse } from "@/lib/types";

export async function getUsers(params: { offset?: number; limit?: number } = {}): Promise<PaginatedResponse<UserOut>> {
  const sp = new URLSearchParams();
  sp.set("offset", String(params.offset ?? 0));
  sp.set("limit", String(params.limit ?? 50));
  return apiFetch(`/users?${sp.toString()}`);
}

export async function getUser(id: string): Promise<UserWithRoles> {
  return apiFetch(`/users/${id}`);
}

export async function createUser(body: { username: string; email: string; password: string }): Promise<UserOut> {
  return apiFetch("/users", { method: "POST", body: JSON.stringify(body) });
}

export async function updateUser(id: string, body: { email?: string; is_active?: boolean }): Promise<UserOut> {
  return apiFetch(`/users/${id}`, { method: "PATCH", body: JSON.stringify(body) });
}

export async function getUserGroups(userId: string): Promise<GroupOut[]> {
  return apiFetch(`/users/${userId}/groups`);
}

export async function addUserToGroup(userId: string, groupId: string): Promise<void> {
  return apiFetch(`/users/${userId}/groups`, { method: "POST", body: JSON.stringify({ group_id: groupId }) });
}

export async function removeUserFromGroup(userId: string, groupId: string): Promise<void> {
  return apiFetch(`/users/${userId}/groups/${groupId}`, { method: "DELETE" });
}
