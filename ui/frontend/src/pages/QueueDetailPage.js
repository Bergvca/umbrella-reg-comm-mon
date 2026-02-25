import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useParams, Link, useSearchParams } from "react-router";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { AlertTable } from "@/components/alerts/AlertTable";
import { BatchTable } from "@/components/queues/BatchTable";
import { useQueue, useQueueBatches, useGenerateBatches, useBatchAlerts } from "@/hooks/useQueues";
import { useAuthStore } from "@/stores/auth";
import { hasRole } from "@/lib/utils";
export function QueueDetailPage() {
    const { id } = useParams();
    const queueId = id ?? "";
    const [searchParams] = useSearchParams();
    const batchId = searchParams.get("batch") ?? "";
    const user = useAuthStore((s) => s.user);
    const canManage = user ? hasRole(user.roles, "supervisor") : false;
    const { data: queue, isLoading, isError } = useQueue(queueId);
    const { data: batches, isLoading: loadingBatches } = useQueueBatches(queueId);
    const generateMutation = useGenerateBatches(queueId);
    const { data: batchAlerts, isLoading: loadingAlerts } = useBatchAlerts(queueId, batchId);
    if (isLoading) {
        return (_jsxs("div", { className: "p-6 space-y-4", children: [_jsx(Skeleton, { className: "h-6 w-32" }), _jsx(Skeleton, { className: "h-24 w-full" })] }));
    }
    if (isError || !queue) {
        return (_jsx("div", { className: "p-6", children: _jsx(Card, { children: _jsxs(CardContent, { className: "pt-6 text-center space-y-3", children: [_jsx("p", { className: "text-muted-foreground", children: "Queue not found." }), _jsx(Link, { to: "/queues", className: "text-sm text-primary hover:underline", children: "Back to Queues" })] }) }) }));
    }
    return (_jsxs("div", { className: "p-6 space-y-6 max-w-3xl", children: [_jsx(Link, { to: "/queues", className: "text-sm text-muted-foreground hover:text-foreground", children: "Back to Queues" }), _jsxs("div", { children: [_jsx("h1", { className: "text-2xl font-semibold", children: queue.name }), queue.description && (_jsx("p", { className: "text-muted-foreground mt-1", children: queue.description }))] }), _jsxs("dl", { className: "flex gap-6 text-sm", children: [_jsxs("div", { children: [_jsx("dt", { className: "text-muted-foreground", children: "Batches" }), _jsx("dd", { className: "font-medium", children: queue.batch_count })] }), _jsxs("div", { children: [_jsx("dt", { className: "text-muted-foreground", children: "Total Items" }), _jsx("dd", { className: "font-medium", children: queue.total_items })] })] }), _jsxs("div", { className: "space-y-3", children: [_jsxs("div", { className: "flex items-center justify-between", children: [_jsx("h2", { className: "text-base font-semibold", children: "Batches" }), canManage && (_jsx(Button, { size: "sm", onClick: () => generateMutation.mutate(), disabled: generateMutation.isPending, children: generateMutation.isPending ? "Generating..." : "Generate Batches" }))] }), generateMutation.isError && (_jsx("p", { className: "text-sm text-destructive", children: generateMutation.error?.message ?? "Failed to generate batches" })), loadingBatches ? (_jsxs("div", { className: "space-y-2", children: [_jsx(Skeleton, { className: "h-16 w-full" }), _jsx(Skeleton, { className: "h-16 w-full" })] })) : (_jsx(BatchTable, { queueId: queueId, batches: batches ?? [], canManage: canManage }))] }), batchId && (_jsxs("div", { children: [_jsx("h2", { className: "text-base font-semibold mb-3", children: "Batch Alerts" }), _jsx(AlertTable, { data: batchAlerts, total: batchAlerts?.length ?? 0, offset: 0, limit: 50, onPageChange: () => { }, isLoading: loadingAlerts })] }))] }));
}
