import { jsx as _jsx } from "react/jsx-runtime";
import { Skeleton } from "@/components/ui/skeleton";
import { BatchCard } from "./BatchCard";
import { useMyQueue } from "@/hooks/useQueues";
export function MyQueueList() {
    const { data: batches, isLoading, isError } = useMyQueue();
    if (isLoading) {
        return (_jsx("div", { className: "space-y-3", children: Array.from({ length: 3 }).map((_, i) => (_jsx(Skeleton, { className: "h-24 w-full" }, i))) }));
    }
    if (isError) {
        return _jsx("p", { className: "text-sm text-destructive", children: "Failed to load your queue." });
    }
    if (!batches || batches.length === 0) {
        return (_jsx("p", { className: "text-sm text-muted-foreground", children: "No batches assigned to you." }));
    }
    return (_jsx("div", { className: "space-y-3", children: batches.map((batch) => (_jsx(BatchCard, { batch: batch }, batch.id))) }));
}
