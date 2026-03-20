import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useState } from "react";
import { useGroupPolicies, useAssignGroupPolicy, useRemoveGroupPolicy } from "@/hooks/usePolicies";
import { useGroups } from "@/hooks/useGroups";
export function GroupPolicyManager({ policyId, canEdit }) {
    const { data: assignments } = useGroupPolicies(policyId);
    const { data: groupsData } = useGroups();
    const assignMutation = useAssignGroupPolicy(policyId);
    const removeMutation = useRemoveGroupPolicy(policyId);
    const [selectedGroup, setSelectedGroup] = useState("");
    const assignedGroupIds = new Set(assignments?.map((a) => a.group_id));
    const availableGroups = groupsData?.items?.filter((g) => !assignedGroupIds.has(g.id)) ?? [];
    return (_jsxs("div", { className: "space-y-2", children: [assignments?.map((a) => (_jsxs("div", { className: "flex items-center gap-3 border rounded p-2 text-sm", children: [_jsx("span", { className: "flex-1", children: a.group_name ?? a.group_id }), canEdit && (_jsx(Button, { size: "sm", variant: "ghost", className: "text-destructive hover:text-destructive", onClick: () => removeMutation.mutate(a.group_id), children: "Remove" }))] }, a.group_id))), !assignments?.length && _jsx("p", { className: "text-sm text-muted-foreground", children: "No groups assigned." }), canEdit && availableGroups.length > 0 && (_jsxs("div", { className: "flex gap-2 items-center pt-1", children: [_jsxs(Select, { value: selectedGroup, onValueChange: setSelectedGroup, children: [_jsx(SelectTrigger, { className: "w-48", children: _jsx(SelectValue, { placeholder: "Add group\u2026" }) }), _jsx(SelectContent, { children: availableGroups.map((g) => (_jsx(SelectItem, { value: String(g.id), children: g.name }, g.id))) })] }), _jsx(Button, { size: "sm", disabled: !selectedGroup || assignMutation.isPending, onClick: () => { assignMutation.mutate(selectedGroup, { onSuccess: () => setSelectedGroup("") }); }, children: "Assign" })] }))] }));
}
