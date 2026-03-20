import { useQuery } from "@tanstack/react-query";
import { searchMessages, getMessage, nlSearchMessages } from "@/api/messages";
export function useMessageSearch(params) {
    return useQuery({
        queryKey: ["messages", "search", params],
        queryFn: () => searchMessages(params),
        enabled: !!(params.q || params.channel || params.participant || params.date_from),
    });
}
export function useNLSearch(query, offset = 0, limit = 20, modelId) {
    return useQuery({
        queryKey: ["messages", "nl-search", query, offset, limit, modelId],
        queryFn: () => nlSearchMessages({ query, model_id: modelId, offset, limit }),
        enabled: !!query,
    });
}
export function useMessage(index, docId) {
    return useQuery({
        queryKey: ["messages", index, docId],
        queryFn: () => getMessage(index, docId),
        enabled: !!index && !!docId,
    });
}
