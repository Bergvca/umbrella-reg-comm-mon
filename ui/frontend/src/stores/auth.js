import { create } from "zustand";
import { persist } from "zustand/middleware";
export const useAuthStore = create()(persist((set) => ({
    accessToken: null,
    refreshToken: null,
    user: null,
    isAuthenticated: false,
    setTokens: (access, refresh) => set({ accessToken: access, refreshToken: refresh, isAuthenticated: true }),
    setUser: (user) => set({ user }),
    logout: () => set({
        accessToken: null,
        refreshToken: null,
        user: null,
        isAuthenticated: false,
    }),
}), {
    name: "umbrella-auth",
}));
