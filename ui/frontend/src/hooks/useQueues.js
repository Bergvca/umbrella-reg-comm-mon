import { useQuery } from "@tanstack/react-query";
import { getQueues, getQueue, getBatchItems, getMyQueue } from "@/api/queues";
export function useQueues(params = {}) {
    return useQuery({
        queryKey: ["queues", "list", params],
        queryFn: () => getQueues(params),
    });
}
export function useQueue(id) {
    return useQuery({
        queryKey: ["queues", id],
        queryFn: () => getQueue(id),
        enabled: !!id,
    });
}
export function useBatchItems(queueId, batchId) {
    return useQuery({
        queryKey: ["batches", batchId, "items"],
        queryFn: () => getBatchItems(queueId, batchId),
        enabled: !!queueId && !!batchId,
    });
}
export function useMyQueue() {
    return useQuery({
        queryKey: ["my-queue"],
        queryFn: getMyQueue,
        refetchInterval: 30_000,
    });
}
