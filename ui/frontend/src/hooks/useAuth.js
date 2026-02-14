import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router";
import { login, getMe } from "@/api/auth";
import { useAuthStore } from "@/stores/auth";
export function useLogin() {
    const { setTokens, setUser } = useAuthStore();
    const navigate = useNavigate();
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (credentials) => login(credentials),
        onSuccess: async (data) => {
            setTokens(data.access_token, data.refresh_token);
            // Fetch user profile immediately after login
            const user = await getMe();
            setUser(user);
            queryClient.setQueryData(["auth", "me"], user);
            void navigate("/");
        },
    });
}
export function useCurrentUser() {
    const { isAuthenticated, setUser } = useAuthStore();
    return useQuery({
        queryKey: ["auth", "me"],
        queryFn: async () => {
            const user = await getMe();
            setUser(user);
            return user;
        },
        enabled: isAuthenticated,
        staleTime: 5 * 60 * 1000, // 5 minutes
    });
}
export function useLogout() {
    const { logout } = useAuthStore();
    const navigate = useNavigate();
    const queryClient = useQueryClient();
    return () => {
        logout();
        queryClient.clear();
        void navigate("/login");
    };
}
