import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router";
import { useCallback } from "react";
import { login, getMe } from "@/api/auth";
import { useAuthStore } from "@/stores/auth";
export function useLogin() {
    const setTokens = useAuthStore((s) => s.setTokens);
    const setUser = useAuthStore((s) => s.setUser);
    const navigate = useNavigate();
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (credentials) => login(credentials),
        onSuccess: async (data) => {
            setTokens(data.access_token, data.refresh_token);
            const user = await getMe();
            setUser(user);
            queryClient.setQueryData(["auth", "me"], user);
            void navigate("/");
        },
    });
}
export function useCurrentUser() {
    const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
    return useQuery({
        queryKey: ["auth", "me"],
        queryFn: getMe,
        enabled: isAuthenticated,
        staleTime: 5 * 60 * 1000, // 5 minutes
    });
}
export function useLogout() {
    const logout = useAuthStore((s) => s.logout);
    const navigate = useNavigate();
    const queryClient = useQueryClient();
    return useCallback(() => {
        logout();
        queryClient.clear();
        void navigate("/login");
    }, [logout, navigate, queryClient]);
}
