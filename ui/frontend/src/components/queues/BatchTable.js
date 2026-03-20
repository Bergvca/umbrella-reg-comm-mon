import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Badge } from "@/components/ui/badge";
import { BatchAssignDialog } from "./BatchAssignDialog";
import { AddItemDialog } from "./AddItemDialog";
import { formatDateTime } from "@/lib/utils";
export function BatchTable({ queueId, batches, canManage }) {
    if (!batches.length) {
        return _jsx("p", { className: "text-sm text-muted-foreground", children: "No batches yet." });
    }
    return (_jsx("div", { className: "space-y-3", children: batches.map((batch) => (_jsxs("div", { className: "border rounded-lg p-4 space-y-2", children: [_jsxs("div", { className: "flex items-center gap-3", children: [_jsx("span", { className: "font-medium text-sm flex-1", children: batch.name }), _jsx(Badge, { variant: batch.status === "in_progress" ? "default" : batch.status === "completed" ? "secondary" : "outline", children: batch.status }), canManage && _jsx(BatchAssignDialog, { queueId: queueId, batch: batch }), canManage && _jsx(AddItemDialog, { queueId: queueId, batchId: batch.id })] }), batch.assigned_to && (_jsxs("p", { className: "text-xs text-muted-foreground", children: ["Assigned to: ", batch.assigned_to] })), batch.created_at && (_jsxs("p", { className: "text-xs text-muted-foreground", children: ["Created: ", formatDateTime(batch.created_at)] })), batch.item_count != null && (_jsxs("p", { className: "text-xs text-muted-foreground", children: [batch.item_count, " items"] }))] }, batch.id))) }));
}
