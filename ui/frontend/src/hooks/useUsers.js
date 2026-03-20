import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import * as api from "@/api/users";
export function useUsers(params = {}) {
    return useQuery({
        queryKey: ["users", "list", params],
        queryFn: () => api.getUsers(params),
    });
}
export function useUser(id) {
    return useQuery({
        queryKey: ["users", id],
        queryFn: () => api.getUser(id),
        enabled: !!id,
    });
}
export function useCreateUser() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: api.createUser,
        onSuccess: () => { void qc.invalidateQueries({ queryKey: ["users"] }); },
    });
}
export function useUpdateUser() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: ({ id, ...body }) => api.updateUser(id, body),
        onSuccess: () => { void qc.invalidateQueries({ queryKey: ["users"] }); },
    });
}
export function useUserGroups(userId) {
    return useQuery({
        queryKey: ["users", userId, "groups"],
        queryFn: () => api.getUserGroups(userId),
        enabled: !!userId,
    });
}
export function useAddUserToGroup(userId) {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: (groupId) => api.addUserToGroup(userId, groupId),
        onSuccess: () => { void qc.invalidateQueries({ queryKey: ["users", userId, "groups"] }); },
    });
}
export function useRemoveUserFromGroup(userId) {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: (groupId) => api.removeUserFromGroup(userId, groupId),
        onSuccess: () => { void qc.invalidateQueries({ queryKey: ["users", userId, "groups"] }); },
    });
}
