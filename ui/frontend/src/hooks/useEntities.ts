import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getEntities,
  getEntity,
  getEntityMessages,
  getEntityAlerts,
  createEntity,
  updateEntity,
  deleteEntity,
  addHandle,
  removeHandle,
  addAttribute,
  removeAttribute,
  batchUploadJson,
  batchUploadCsv,
} from "@/api/entities";
import type { EntityListParams, EntityCreateBody } from "@/api/entities";

export function useEntities(params: EntityListParams) {
  return useQuery({
    queryKey: ["entities", "list", params],
    queryFn: () => getEntities(params),
  });
}

export function useEntity(id: string) {
  return useQuery({
    queryKey: ["entities", id],
    queryFn: () => getEntity(id),
    enabled: !!id,
  });
}

export function useEntityMessages(id: string, params: { offset?: number; limit?: number } = {}) {
  return useQuery({
    queryKey: ["entities", id, "messages", params],
    queryFn: () => getEntityMessages(id, params),
    enabled: !!id,
  });
}

export function useEntityAlerts(id: string) {
  return useQuery({
    queryKey: ["entities", id, "alerts"],
    queryFn: () => getEntityAlerts(id),
    enabled: !!id,
  });
}

export function useCreateEntity() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: EntityCreateBody) => createEntity(body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["entities", "list"] });
    },
  });
}

export function useUpdateEntity() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: { display_name?: string; entity_type?: string } }) =>
      updateEntity(id, body),
    onSuccess: (_data, { id }) => {
      void qc.invalidateQueries({ queryKey: ["entities", id] });
      void qc.invalidateQueries({ queryKey: ["entities", "list"] });
    },
  });
}

export function useDeleteEntity() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteEntity(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["entities", "list"] });
    },
  });
}

export function useAddHandle() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ entityId, body }: { entityId: string; body: { handle_type: string; handle_value: string; is_primary?: boolean } }) =>
      addHandle(entityId, body),
    onSuccess: (_data, { entityId }) => {
      void qc.invalidateQueries({ queryKey: ["entities", entityId] });
    },
  });
}

export function useRemoveHandle() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ entityId, handleId }: { entityId: string; handleId: string }) =>
      removeHandle(entityId, handleId),
    onSuccess: (_data, { entityId }) => {
      void qc.invalidateQueries({ queryKey: ["entities", entityId] });
    },
  });
}

export function useAddAttribute() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ entityId, body }: { entityId: string; body: { attr_key: string; attr_value: string } }) =>
      addAttribute(entityId, body),
    onSuccess: (_data, { entityId }) => {
      void qc.invalidateQueries({ queryKey: ["entities", entityId] });
    },
  });
}

export function useRemoveAttribute() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ entityId, attrId }: { entityId: string; attrId: string }) =>
      removeAttribute(entityId, attrId),
    onSuccess: (_data, { entityId }) => {
      void qc.invalidateQueries({ queryKey: ["entities", entityId] });
    },
  });
}

export function useBatchUploadJson() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (items: EntityCreateBody[]) => batchUploadJson(items),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["entities", "list"] });
    },
  });
}

export function useBatchUploadCsv() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => batchUploadCsv(file),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["entities", "list"] });
    },
  });
}
