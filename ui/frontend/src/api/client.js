import { useAuthStore } from "@/stores/auth";
const BASE_URL = "/api/v1";
export class ApiError extends Error {
    status;
    body;
    constructor(status, body) {
        super(`API error ${status}`);
        this.status = status;
        this.body = body;
        this.name = "ApiError";
    }
}
async function refreshAccessToken() {
    const { refreshToken, setTokens, logout } = useAuthStore.getState();
    if (!refreshToken)
        return null;
    try {
        const res = await fetch(`${BASE_URL}/auth/refresh`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${refreshToken}`,
            },
        });
        if (!res.ok) {
            logout();
            return null;
        }
        const data = (await res.json());
        setTokens(data.access_token, data.refresh_token);
        return data.access_token;
    }
    catch {
        logout();
        return null;
    }
}
export async function apiFetch(path, options = {}) {
    const { accessToken } = useAuthStore.getState();
    const headers = new Headers(options.headers);
    if (accessToken) {
        headers.set("Authorization", `Bearer ${accessToken}`);
    }
    if (!headers.has("Content-Type") && options.body) {
        headers.set("Content-Type", "application/json");
    }
    let res = await fetch(`${BASE_URL}${path}`, { ...options, headers });
    // Auto-refresh on 401
    if (res.status === 401 && accessToken) {
        const newToken = await refreshAccessToken();
        if (newToken) {
            headers.set("Authorization", `Bearer ${newToken}`);
            res = await fetch(`${BASE_URL}${path}`, { ...options, headers });
        }
    }
    if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new ApiError(res.status, body);
    }
    // Handle 204 No Content
    if (res.status === 204)
        return undefined;
    return res.json();
}
