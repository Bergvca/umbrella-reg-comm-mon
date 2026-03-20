import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import * as api from "@/api/groups";
export function useGroups(params = {}) {
    return useQuery({
        queryKey: ["groups", "list", params],
        queryFn: () => api.getGroups(params),
    });
}
export function useGroup(id) {
    return useQuery({
        queryKey: ["groups", id],
        queryFn: () => api.getGroup(id),
        enabled: !!id,
    });
}
export function useCreateGroup() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: api.createGroup,
        onSuccess: () => { void qc.invalidateQueries({ queryKey: ["groups"] }); },
    });
}
export function useUpdateGroup() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: ({ id, ...body }) => api.updateGroup(id, body),
        onSuccess: () => { void qc.invalidateQueries({ queryKey: ["groups"] }); },
    });
}
export function useGroupMembers(groupId) {
    return useQuery({
        queryKey: ["groups", groupId, "members"],
        queryFn: () => api.getGroupMembers(groupId),
        enabled: !!groupId,
    });
}
export function useAssignRoleToGroup(groupId) {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: (roleId) => api.assignRoleToGroup(groupId, roleId),
        onSuccess: () => { void qc.invalidateQueries({ queryKey: ["groups", groupId] }); },
    });
}
export function useRemoveRoleFromGroup(groupId) {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: (roleId) => api.removeRoleFromGroup(groupId, roleId),
        onSuccess: () => { void qc.invalidateQueries({ queryKey: ["groups", groupId] }); },
    });
}
