import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useState } from "react";
import { useUserGroups, useAddUserToGroup, useRemoveUserFromGroup } from "@/hooks/useUsers";
import { useGroups } from "@/hooks/useGroups";
export function UserGroupManager({ userId }) {
    const { data: userGroups } = useUserGroups(userId);
    const { data: allGroupsData } = useGroups();
    const addMutation = useAddUserToGroup(userId);
    const removeMutation = useRemoveUserFromGroup(userId);
    const [selectedGroup, setSelectedGroup] = useState("");
    const userGroupIds = new Set(userGroups?.map((g) => g.id));
    const availableGroups = allGroupsData?.items?.filter((g) => !userGroupIds.has(g.id)) ?? [];
    return (_jsxs("div", { className: "space-y-2", children: [_jsx("p", { className: "text-sm font-medium", children: "Group Memberships" }), userGroups?.map((g) => (_jsxs("div", { className: "flex items-center gap-2 border rounded p-2 text-sm", children: [_jsx("span", { className: "flex-1", children: g.name }), _jsx(Button, { size: "sm", variant: "ghost", className: "text-destructive hover:text-destructive", onClick: () => removeMutation.mutate(g.id), children: "Remove" })] }, g.id))), !userGroups?.length && _jsx("p", { className: "text-xs text-muted-foreground", children: "No group memberships." }), availableGroups.length > 0 && (_jsxs("div", { className: "flex gap-2 items-center pt-1", children: [_jsxs(Select, { value: selectedGroup, onValueChange: setSelectedGroup, children: [_jsx(SelectTrigger, { className: "w-48", children: _jsx(SelectValue, { placeholder: "Add to group\u2026" }) }), _jsx(SelectContent, { children: availableGroups.map((g) => (_jsx(SelectItem, { value: String(g.id), children: g.name }, g.id))) })] }), _jsx(Button, { size: "sm", disabled: !selectedGroup || addMutation.isPending, onClick: () => { addMutation.mutate(selectedGroup, { onSuccess: () => setSelectedGroup("") }); }, children: "Add" })] }))] }));
}
