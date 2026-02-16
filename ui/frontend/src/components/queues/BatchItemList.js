import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Link } from "react-router";
import { Skeleton } from "@/components/ui/skeleton";
import { formatRelative } from "@/lib/utils";
import { useBatchItems } from "@/hooks/useQueues";
export function BatchItemList({ queueId, batchId }) {
    const { data: items, isLoading, isError } = useBatchItems(queueId, batchId);
    if (isLoading) {
        return (_jsx("div", { className: "space-y-2", children: Array.from({ length: 4 }).map((_, i) => (_jsx(Skeleton, { className: "h-8 w-full" }, i))) }));
    }
    if (isError) {
        return _jsx("p", { className: "text-sm text-destructive", children: "Failed to load batch items." });
    }
    if (!items || items.length === 0) {
        return _jsx("p", { className: "text-sm text-muted-foreground", children: "No items in this batch." });
    }
    return (_jsx("ol", { className: "space-y-1", children: items.map((item) => (_jsxs("li", { className: "flex items-center gap-3 text-sm py-1.5 border-b last:border-0", children: [_jsxs("span", { className: "text-muted-foreground w-6 text-right shrink-0", children: [item.position, "."] }), _jsx(Link, { to: `/alerts/${item.alert_id}`, className: "font-mono text-xs text-primary hover:underline truncate", children: item.alert_id }), _jsx("span", { className: "text-muted-foreground text-xs ml-auto shrink-0", children: formatRelative(item.created_at) })] }, item.id))) }));
}
