import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useQueues } from "@/hooks/useQueues";
export function DecisionStatusTable() {
    const { data: queues, isLoading } = useQueues();
    if (isLoading)
        return _jsx(Skeleton, { className: "h-32 w-full" });
    return (_jsxs("div", { className: "border rounded-lg divide-y", children: [!queues?.items?.length && _jsx("p", { className: "p-4 text-sm text-muted-foreground", children: "No queues." }), queues?.items?.map((q) => (_jsxs("div", { className: "flex items-center gap-3 p-3", children: [_jsxs("div", { className: "flex-1", children: [_jsx("p", { className: "text-sm font-medium", children: q.name }), q.description && _jsx("p", { className: "text-xs text-muted-foreground", children: q.description })] }), _jsx(Badge, { variant: "outline", children: q.channel }), _jsx(Badge, { variant: q.is_active ? "default" : "secondary", children: q.is_active ? "Active" : "Inactive" })] }, q.id)))] }));
}
