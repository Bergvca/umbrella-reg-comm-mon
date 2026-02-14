import { apiFetch } from "./client";
export async function login(credentials) {
    return apiFetch("/auth/login", {
        method: "POST",
        body: JSON.stringify(credentials),
    });
}
export async function refreshToken() {
    return apiFetch("/auth/refresh", {
        method: "POST",
    });
}
export async function getMe() {
    return apiFetch("/auth/me");
}
