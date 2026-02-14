import { create } from "zustand";
export const useAuthStore = create((set) => ({
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
}));
