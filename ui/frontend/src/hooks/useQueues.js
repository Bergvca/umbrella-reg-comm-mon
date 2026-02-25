import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getQueues, getQueue, getBatches, getBatchItems, getBatchAlerts, getMyQueue, createQueue, createBatch, generateBatches, updateBatch, addItemToBatch } from "@/api/queues";
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
export function useQueueBatches(queueId) {
    return useQuery({
        queryKey: ["queues", queueId, "batches"],
        queryFn: () => getBatches(queueId),
        enabled: !!queueId,
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
export function useCreateQueue() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: createQueue,
        onSuccess: () => { void qc.invalidateQueries({ queryKey: ["queues"] }); },
    });
}
export function useBatchAlerts(queueId, batchId) {
    return useQuery({
        queryKey: ["queues", queueId, "batches", batchId, "alerts"],
        queryFn: () => getBatchAlerts(queueId, batchId),
        enabled: !!queueId && !!batchId,
    });
}
export function useGenerateBatches(queueId) {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: () => generateBatches(queueId),
        onSuccess: () => {
            void qc.invalidateQueries({ queryKey: ["queues", queueId] });
            void qc.invalidateQueries({ queryKey: ["queues", queueId, "batches"] });
        },
    });
}
export function useCreateBatch(queueId) {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: (body) => createBatch(queueId, body),
        onSuccess: () => {
            void qc.invalidateQueries({ queryKey: ["queues", queueId] });
            void qc.invalidateQueries({ queryKey: ["queues", queueId, "batches"] });
        },
    });
}
export function useUpdateBatch(queueId) {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: ({ batchId, ...body }) => updateBatch(queueId, batchId, body),
        onSuccess: () => { void qc.invalidateQueries({ queryKey: ["queues", queueId] }); },
    });
}
export function useAddItemToBatch(queueId, batchId) {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: (body) => addItemToBatch(queueId, batchId, body),
        onSuccess: () => { void qc.invalidateQueries({ queryKey: ["batches", batchId, "items"] }); },
    });
}
