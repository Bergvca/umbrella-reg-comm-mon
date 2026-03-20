import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDateTime } from "@/lib/utils";
import { AuditDetailDialog } from "./AuditDetailDialog";
export function AuditLogTable({ entries, isLoading }) {
    const [selected, setSelected] = useState(null);
    if (isLoading)
        return _jsx(Skeleton, { className: "h-64 w-full" });
    if (!entries.length)
        return _jsx("p", { className: "text-sm text-muted-foreground text-center py-8", children: "No audit events found." });
    return (_jsxs(_Fragment, { children: [_jsx("div", { className: "border rounded-lg divide-y", children: entries.map((entry) => (_jsxs("div", { className: "flex items-center gap-3 p-3 cursor-pointer hover:bg-muted/50 transition-colors", onClick: () => setSelected(entry), children: [_jsxs("div", { className: "flex-1 min-w-0", children: [_jsxs("div", { className: "flex items-center gap-2", children: [_jsx(Badge, { variant: "outline", className: "text-xs", children: entry.object_type }), _jsx("span", { className: "text-sm font-medium", children: entry.action })] }), _jsxs("p", { className: "text-xs text-muted-foreground mt-0.5", children: [entry.actor_id ?? "System", " \u00B7 ", formatDateTime(entry.occurred_at)] })] }), _jsxs("span", { className: "text-xs text-muted-foreground shrink-0", children: ["#", entry.object_id] })] }, entry.id))) }), _jsx(AuditDetailDialog, { entry: selected, onClose: () => setSelected(null) })] }));
}
