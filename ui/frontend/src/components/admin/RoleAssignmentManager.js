import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { useState } from "react";
import { useAssignRoleToGroup, useRemoveRoleFromGroup } from "@/hooks/useGroups";
import { useRoles } from "@/hooks/useRoles";
export function RoleAssignmentManager({ groupId, assignedRoles }) {
    const { data: allRoles } = useRoles();
    const assignMutation = useAssignRoleToGroup(groupId);
    const removeMutation = useRemoveRoleFromGroup(groupId);
    const [selectedRole, setSelectedRole] = useState("");
    const assignedRoleIds = new Set(assignedRoles.map((r) => r.id));
    const availableRoles = allRoles?.filter((r) => !assignedRoleIds.has(r.id)) ?? [];
    return (_jsxs("div", { className: "space-y-2", children: [_jsx("p", { className: "text-sm font-medium", children: "Roles" }), _jsxs("div", { className: "flex flex-wrap gap-2", children: [assignedRoles.map((r) => (_jsxs(Badge, { variant: "secondary", className: "flex items-center gap-1", children: [r.name, _jsx("button", { className: "ml-1 text-muted-foreground hover:text-foreground", onClick: () => removeMutation.mutate(r.id), children: "\u00D7" })] }, r.id))), !assignedRoles.length && _jsx("span", { className: "text-xs text-muted-foreground", children: "No roles assigned." })] }), availableRoles.length > 0 && (_jsxs("div", { className: "flex gap-2 items-center", children: [_jsxs(Select, { value: selectedRole, onValueChange: setSelectedRole, children: [_jsx(SelectTrigger, { className: "w-40", children: _jsx(SelectValue, { placeholder: "Add role\u2026" }) }), _jsx(SelectContent, { children: availableRoles.map((r) => (_jsx(SelectItem, { value: String(r.id), children: r.name }, r.id))) })] }), _jsx(Button, { size: "sm", disabled: !selectedRole || assignMutation.isPending, onClick: () => { assignMutation.mutate(selectedRole, { onSuccess: () => setSelectedRole("") }); }, children: "Add" })] }))] }));
}
