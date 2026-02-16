import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import * as api from "@/api/users";

export function useUsers(params: { offset?: number; limit?: number } = {}) {
  return useQuery({
    queryKey: ["users", "list", params],
    queryFn: () => api.getUsers(params),
  });
}

export function useUser(id: string) {
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
    mutationFn: ({ id, ...body }: { id: string; email?: string; full_name?: string; is_active?: boolean }) =>
      api.updateUser(id, body),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ["users"] }); },
  });
}

export function useUserGroups(userId: string) {
  return useQuery({
    queryKey: ["users", userId, "groups"],
    queryFn: () => api.getUserGroups(userId),
    enabled: !!userId,
  });
}

export function useAddUserToGroup(userId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (groupId: string) => api.addUserToGroup(userId, groupId),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ["users", userId, "groups"] }); },
  });
}

export function useRemoveUserFromGroup(userId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (groupId: string) => api.removeUserFromGroup(userId, groupId),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ["users", userId, "groups"] }); },
  });
}
