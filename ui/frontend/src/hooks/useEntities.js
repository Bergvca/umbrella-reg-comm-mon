import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getEntities, getEntity, getEntityMessages, getEntityAlerts, createEntity, updateEntity, deleteEntity, addHandle, removeHandle, addAttribute, removeAttribute, batchUploadJson, batchUploadCsv, } from "@/api/entities";
export function useEntities(params) {
    return useQuery({
        queryKey: ["entities", "list", params],
        queryFn: () => getEntities(params),
    });
}
export function useEntity(id) {
    return useQuery({
        queryKey: ["entities", id],
        queryFn: () => getEntity(id),
        enabled: !!id,
    });
}
export function useEntityMessages(id, params = {}) {
    return useQuery({
        queryKey: ["entities", id, "messages", params],
        queryFn: () => getEntityMessages(id, params),
        enabled: !!id,
    });
}
export function useEntityAlerts(id) {
    return useQuery({
        queryKey: ["entities", id, "alerts"],
        queryFn: () => getEntityAlerts(id),
        enabled: !!id,
    });
}
export function useCreateEntity() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: (body) => createEntity(body),
        onSuccess: () => {
            void qc.invalidateQueries({ queryKey: ["entities", "list"] });
        },
    });
}
export function useUpdateEntity() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: ({ id, body }) => updateEntity(id, body),
        onSuccess: (_data, { id }) => {
            void qc.invalidateQueries({ queryKey: ["entities", id] });
            void qc.invalidateQueries({ queryKey: ["entities", "list"] });
        },
    });
}
export function useDeleteEntity() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: (id) => deleteEntity(id),
        onSuccess: () => {
            void qc.invalidateQueries({ queryKey: ["entities", "list"] });
        },
    });
}
export function useAddHandle() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: ({ entityId, body }) => addHandle(entityId, body),
        onSuccess: (_data, { entityId }) => {
            void qc.invalidateQueries({ queryKey: ["entities", entityId] });
        },
    });
}
export function useRemoveHandle() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: ({ entityId, handleId }) => removeHandle(entityId, handleId),
        onSuccess: (_data, { entityId }) => {
            void qc.invalidateQueries({ queryKey: ["entities", entityId] });
        },
    });
}
export function useAddAttribute() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: ({ entityId, body }) => addAttribute(entityId, body),
        onSuccess: (_data, { entityId }) => {
            void qc.invalidateQueries({ queryKey: ["entities", entityId] });
        },
    });
}
export function useRemoveAttribute() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: ({ entityId, attrId }) => removeAttribute(entityId, attrId),
        onSuccess: (_data, { entityId }) => {
            void qc.invalidateQueries({ queryKey: ["entities", entityId] });
        },
    });
}
export function useBatchUploadJson() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: (items) => batchUploadJson(items),
        onSuccess: () => {
            void qc.invalidateQueries({ queryKey: ["entities", "list"] });
        },
    });
}
export function useBatchUploadCsv() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: (file) => batchUploadCsv(file),
        onSuccess: () => {
            void qc.invalidateQueries({ queryKey: ["entities", "list"] });
        },
    });
}
