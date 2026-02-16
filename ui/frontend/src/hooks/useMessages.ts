import { useQuery } from "@tanstack/react-query";
import { searchMessages, getMessage } from "@/api/messages";
import type { MessageSearchParams } from "@/api/messages";

export function useMessageSearch(params: MessageSearchParams) {
  return useQuery({
    queryKey: ["messages", "search", params],
    queryFn: () => searchMessages(params),
    enabled: !!(params.q || params.channel || params.participant || params.date_from),
  });
}

export function useMessage(index: string, docId: string) {
  return useQuery({
    queryKey: ["messages", index, docId],
    queryFn: () => getMessage(index, docId),
    enabled: !!index && !!docId,
  });
}
