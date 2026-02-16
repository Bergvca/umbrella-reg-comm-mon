import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useNavigate } from "react-router";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { formatRelative } from "@/lib/utils";
const STATUS_CLASSES = {
    pending: "text-muted-foreground border-muted",
    in_progress: "text-yellow-600 border-yellow-300",
    completed: "text-green-600 border-green-300",
};
export function BatchCard({ batch }) {
    const navigate = useNavigate();
    return (_jsx(Card, { children: _jsx(CardContent, { className: "pt-4 pb-4", children: _jsxs("div", { className: "flex items-start justify-between gap-4", children: [_jsxs("div", { className: "space-y-1", children: [_jsxs("div", { className: "flex items-center gap-2", children: [_jsx("span", { className: "font-medium", children: batch.name ?? "Unnamed Batch" }), _jsx(Badge, { variant: "outline", className: STATUS_CLASSES[batch.status], children: batch.status.replace("_", " ") })] }), _jsxs("p", { className: "text-sm text-muted-foreground", children: ["Queue: ", batch.queue_id, " \u00B7 Items: ", batch.item_count] }), batch.assigned_at && (_jsxs("p", { className: "text-xs text-muted-foreground", children: ["Assigned ", formatRelative(batch.assigned_at)] }))] }), _jsx(Button, { variant: "outline", size: "sm", onClick: () => void navigate(`/queues/${batch.queue_id}?batch=${batch.id}`), children: "Review Batch \u2192" })] }) }) }));
}
