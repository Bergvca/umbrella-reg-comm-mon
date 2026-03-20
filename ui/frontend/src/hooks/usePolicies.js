import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import * as policiesApi from "@/api/policies";
export function usePolicies(params = {}) {
    return useQuery({
        queryKey: ["policies", "list", params],
        queryFn: () => policiesApi.getPolicies(params),
    });
}
export function usePolicy(id) {
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
        mutationFn: ({ id, ...body }) => policiesApi.updatePolicy(id, body),
        onSuccess: () => { void qc.invalidateQueries({ queryKey: ["policies"] }); },
    });
}
export function useRules(policyId, params = {}) {
    return useQuery({
        queryKey: ["rules", policyId, params],
        queryFn: () => policiesApi.getRules(policyId, params),
        enabled: !!policyId,
    });
}
export function useCreateRule(policyId) {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: (body) => policiesApi.createRule(policyId, body),
        onSuccess: () => {
            void qc.invalidateQueries({ queryKey: ["rules", policyId] });
            void qc.invalidateQueries({ queryKey: ["policies"] });
        },
    });
}
export function useUpdateRule(policyId) {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: ({ ruleId, ...body }) => policiesApi.updateRule(ruleId, body),
        onSuccess: () => { void qc.invalidateQueries({ queryKey: ["rules", policyId] }); },
    });
}
export function useDeleteRule(policyId) {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: policiesApi.deleteRule,
        onSuccess: () => { void qc.invalidateQueries({ queryKey: ["rules", policyId] }); },
    });
}
export function useGroupPolicies(policyId) {
    return useQuery({
        queryKey: ["policies", policyId, "groups"],
        queryFn: () => policiesApi.getGroupPolicies(policyId),
        enabled: !!policyId,
    });
}
export function useAssignGroupPolicy(policyId) {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: (groupId) => policiesApi.assignGroupPolicy(policyId, groupId),
        onSuccess: () => {
            void qc.invalidateQueries({ queryKey: ["policies", policyId, "groups"] });
            void qc.invalidateQueries({ queryKey: ["policies"] });
        },
    });
}
export function useRemoveGroupPolicy(policyId) {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: (groupId) => policiesApi.removeGroupPolicy(policyId, groupId),
        onSuccess: () => {
            void qc.invalidateQueries({ queryKey: ["policies", policyId, "groups"] });
            void qc.invalidateQueries({ queryKey: ["policies"] });
        },
    });
}
