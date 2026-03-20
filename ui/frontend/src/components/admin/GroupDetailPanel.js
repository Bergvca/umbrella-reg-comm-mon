import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { useGroupMembers } from "@/hooks/useGroups";
import { RoleAssignmentManager } from "./RoleAssignmentManager";
export function GroupDetailPanel({ group }) {
    const { data: members, isLoading } = useGroupMembers(group.id);
    return (_jsxs("div", { className: "space-y-4", children: [group.description && _jsx("p", { className: "text-sm text-muted-foreground", children: group.description }), _jsx(Separator, {}), _jsx(RoleAssignmentManager, { groupId: group.id, assignedRoles: group.roles ?? [] }), _jsx(Separator, {}), _jsxs("div", { className: "space-y-2", children: [_jsx("p", { className: "text-sm font-medium", children: "Members" }), isLoading && _jsx(Skeleton, { className: "h-16 w-full" }), members?.map((m) => (_jsx("div", { className: "text-sm border rounded p-2", children: m.full_name ?? m.email }, m.id))), !isLoading && !members?.length && (_jsx("p", { className: "text-xs text-muted-foreground", children: "No members." }))] })] }));
}
