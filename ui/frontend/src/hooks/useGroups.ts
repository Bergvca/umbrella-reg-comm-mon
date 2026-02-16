import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import * as api from "@/api/groups";

export function useGroups(params: { offset?: number; limit?: number } = {}) {
  return useQuery({
    queryKey: ["groups", "list", params],
    queryFn: () => api.getGroups(params),
  });
}

export function useGroup(id: string) {
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
    mutationFn: ({ id, ...body }: { id: string; name?: string; description?: string }) =>
      api.updateGroup(id, body),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ["groups"] }); },
  });
}

export function useGroupMembers(groupId: string) {
  return useQuery({
    queryKey: ["groups", groupId, "members"],
    queryFn: () => api.getGroupMembers(groupId),
    enabled: !!groupId,
  });
}

export function useAssignRoleToGroup(groupId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (roleId: string) => api.assignRoleToGroup(groupId, roleId),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ["groups", groupId] }); },
  });
}

export function useRemoveRoleFromGroup(groupId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (roleId: string) => api.removeRoleFromGroup(groupId, roleId),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ["groups", groupId] }); },
  });
}
