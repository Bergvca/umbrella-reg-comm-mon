import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useParams, Link, useSearchParams } from "react-router";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent } from "@/components/ui/card";
import { BatchItemList } from "@/components/queues/BatchItemList";
import { useQueue } from "@/hooks/useQueues";
export function QueueDetailPage() {
    const { id } = useParams();
    const queueId = id ?? "";
    const [searchParams] = useSearchParams();
    const batchId = searchParams.get("batch") ?? "";
    const { data: queue, isLoading, isError } = useQueue(queueId);
    if (isLoading) {
        return (_jsxs("div", { className: "p-6 space-y-4", children: [_jsx(Skeleton, { className: "h-6 w-32" }), _jsx(Skeleton, { className: "h-24 w-full" })] }));
    }
    if (isError || !queue) {
        return (_jsx("div", { className: "p-6", children: _jsx(Card, { children: _jsxs(CardContent, { className: "pt-6 text-center space-y-3", children: [_jsx("p", { className: "text-muted-foreground", children: "Queue not found." }), _jsx(Link, { to: "/queues", className: "text-sm text-primary hover:underline", children: "\u2190 Back to Queues" })] }) }) }));
    }
    return (_jsxs("div", { className: "p-6 space-y-6 max-w-3xl", children: [_jsx(Link, { to: "/queues", className: "text-sm text-muted-foreground hover:text-foreground", children: "\u2190 Back to Queues" }), _jsxs("div", { children: [_jsx("h1", { className: "text-2xl font-semibold", children: queue.name }), queue.description && (_jsx("p", { className: "text-muted-foreground mt-1", children: queue.description }))] }), _jsxs("dl", { className: "flex gap-6 text-sm", children: [_jsxs("div", { children: [_jsx("dt", { className: "text-muted-foreground", children: "Batches" }), _jsx("dd", { className: "font-medium", children: queue.batch_count })] }), _jsxs("div", { children: [_jsx("dt", { className: "text-muted-foreground", children: "Total Items" }), _jsx("dd", { className: "font-medium", children: queue.total_items })] })] }), batchId && (_jsxs("div", { children: [_jsx("h2", { className: "text-base font-semibold mb-3", children: "Batch Items" }), _jsx(BatchItemList, { queueId: queueId, batchId: batchId })] })), !batchId && (_jsx("p", { className: "text-sm text-muted-foreground", children: "Full batch management (create, assign, populate) is Phase 6 scope." }))] }));
}
