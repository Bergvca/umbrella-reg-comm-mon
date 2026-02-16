import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import * as policiesApi from "@/api/policies";

export function usePolicies(params: policiesApi.PolicyListParams = {}) {
  return useQuery({
    queryKey: ["policies", "list", params],
    queryFn: () => policiesApi.getPolicies(params),
  });
}

export function usePolicy(id: string) {
  return useQuery({
    queryKey: ["policies", id],
    queryFn: () => policiesApi.getPolicy(id),
    enabled: !!id,
  });
}

export function useCreatePolicy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: policiesApi.createPolicy,
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ["policies"] }); },
  });
}

export function useUpdatePolicy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: { id: string; name?: string; description?: string; is_active?: boolean }) =>
      policiesApi.updatePolicy(id, body),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ["policies"] }); },
  });
}

export function useRules(policyId: string, params: { offset?: number; limit?: number } = {}) {
  return useQuery({
    queryKey: ["rules", policyId, params],
    queryFn: () => policiesApi.getRules(policyId, params),
    enabled: !!policyId,
  });
}

export function useCreateRule(policyId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string; description?: string; kql: string; severity: string }) =>
      policiesApi.createRule(policyId, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["rules", policyId] });
      void qc.invalidateQueries({ queryKey: ["policies"] });
    },
  });
}

export function useUpdateRule(policyId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ ruleId, ...body }: { ruleId: string; name?: string; description?: string; kql?: string; severity?: string; is_active?: boolean }) =>
      policiesApi.updateRule(ruleId, body),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ["rules", policyId] }); },
  });
}

export function useDeleteRule(policyId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: policiesApi.deleteRule,
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ["rules", policyId] }); },
  });
}

export function useGroupPolicies(policyId: string) {
  return useQuery({
    queryKey: ["policies", policyId, "groups"],
    queryFn: () => policiesApi.getGroupPolicies(policyId),
    enabled: !!policyId,
  });
}

export function useAssignGroupPolicy(policyId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (groupId: string) => policiesApi.assignGroupPolicy(policyId, groupId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["policies", policyId, "groups"] });
      void qc.invalidateQueries({ queryKey: ["policies"] });
    },
  });
}

export function useRemoveGroupPolicy(policyId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (groupId: string) => policiesApi.removeGroupPolicy(policyId, groupId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["policies", policyId, "groups"] });
      void qc.invalidateQueries({ queryKey: ["policies"] });
    },
  });
}
