import { apiFetch } from "./client";
import type { RoleOut } from "@/lib/types";

export async function getRoles(): Promise<RoleOut[]> {
  return apiFetch("/roles");
}
