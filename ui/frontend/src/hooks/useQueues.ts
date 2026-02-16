import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getQueues, getQueue, getBatches, getBatchItems, getMyQueue, createQueue, createBatch, updateBatch, addItemToBatch } from "@/api/queues";

export function useQueues(params: { offset?: number; limit?: number } = {}) {
  return useQuery({
    queryKey: ["queues", "list", params],
    queryFn: () => getQueues(params),
  });
}

export function useQueue(id: string) {
  return useQuery({
    queryKey: ["queues", id],
    queryFn: () => getQueue(id),
    enabled: !!id,
  });
}

export function useQueueBatches(queueId: string) {
  return useQuery({
    queryKey: ["queues", queueId, "batches"],
    queryFn: () => getBatches(queueId),
    enabled: !!queueId,
  });
}

export function useBatchItems(queueId: string, batchId: string) {
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

export function useCreateBatch(queueId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { name?: string }) => createBatch(queueId, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["queues", queueId] });
      void qc.invalidateQueries({ queryKey: ["queues", queueId, "batches"] });
    },
  });
}

export function useUpdateBatch(queueId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ batchId, ...body }: { batchId: string; assigned_to?: string; status?: string }) =>
      updateBatch(queueId, batchId, body),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ["queues", queueId] }); },
  });
}

export function useAddItemToBatch(queueId: string, batchId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { alert_id: string; position: number }) =>
      addItemToBatch(queueId, batchId, body),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ["batches", batchId, "items"] }); },
  });
}
