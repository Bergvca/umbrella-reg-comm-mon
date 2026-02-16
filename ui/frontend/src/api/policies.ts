import { apiFetch } from "./client";
import type { PolicyDetail, PolicyOut, RuleOut, GroupPolicyOut, PaginatedResponse } from "@/lib/types";

export interface PolicyListParams {
  risk_model_id?: string;
  is_active?: boolean;
  offset?: number;
  limit?: number;
}

export async function getPolicies(params: PolicyListParams = {}): Promise<PaginatedResponse<PolicyDetail>> {
  const sp = new URLSearchParams();
  if (params.risk_model_id) sp.set("risk_model_id", params.risk_model_id);
  if (params.is_active !== undefined) sp.set("is_active", String(params.is_active));
  sp.set("offset", String(params.offset ?? 0));
  sp.set("limit", String(params.limit ?? 50));
  return apiFetch(`/policies?${sp.toString()}`);
}

export async function getPolicy(id: string): Promise<PolicyDetail> {
  return apiFetch(`/policies/${id}`);
}

export async function createPolicy(body: { risk_model_id: string; name: string; description?: string }): Promise<PolicyOut> {
  return apiFetch("/policies", { method: "POST", body: JSON.stringify(body) });
}

export async function updatePolicy(id: string, body: { name?: string; description?: string; is_active?: boolean }): Promise<PolicyOut> {
  return apiFetch(`/policies/${id}`, { method: "PATCH", body: JSON.stringify(body) });
}

export async function getRules(policyId: string, params: { offset?: number; limit?: number } = {}): Promise<PaginatedResponse<RuleOut>> {
  const sp = new URLSearchParams();
  sp.set("offset", String(params.offset ?? 0));
  sp.set("limit", String(params.limit ?? 50));
  return apiFetch(`/policies/${policyId}/rules?${sp.toString()}`);
}

export async function createRule(policyId: string, body: { name: string; description?: string; kql: string; severity: string }): Promise<RuleOut> {
  return apiFetch(`/policies/${policyId}/rules`, { method: "POST", body: JSON.stringify(body) });
}

export async function updateRule(ruleId: string, body: { name?: string; description?: string; kql?: string; severity?: string; is_active?: boolean }): Promise<RuleOut> {
  return apiFetch(`/rules/${ruleId}`, { method: "PATCH", body: JSON.stringify(body) });
}

export async function deleteRule(ruleId: string): Promise<void> {
  return apiFetch(`/rules/${ruleId}`, { method: "DELETE" });
}

export async function getGroupPolicies(policyId: string): Promise<GroupPolicyOut[]> {
  return apiFetch(`/policies/${policyId}/groups`);
}

export async function assignGroupPolicy(policyId: string, groupId: string): Promise<void> {
  return apiFetch(`/policies/${policyId}/groups`, { method: "POST", body: JSON.stringify({ group_id: groupId }) });
}

export async function removeGroupPolicy(policyId: string, groupId: string): Promise<void> {
  return apiFetch(`/policies/${policyId}/groups/${groupId}`, { method: "DELETE" });
}
