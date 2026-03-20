import { apiFetch } from "./client";
export async function getRoles() {
    return apiFetch("/roles");
}
