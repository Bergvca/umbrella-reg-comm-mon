import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getDecisions, createDecision, getDecisionStatuses } from "@/api/decisions";
export function useDecisions(alertId) {
    return useQuery({
        queryKey: ["decisions", alertId],
        queryFn: () => getDecisions(alertId),
        enabled: !!alertId,
    });
}
export function useCreateDecision(alertId) {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (body) => createDecision(alertId, body),
        onSuccess: () => {
            void queryClient.invalidateQueries({ queryKey: ["decisions", alertId] });
            void queryClient.invalidateQueries({ queryKey: ["alerts", alertId] });
            void queryClient.invalidateQueries({ queryKey: ["alerts", "list"] });
            void queryClient.invalidateQueries({ queryKey: ["alerts", "stats"] });
        },
    });
}
export function useDecisionStatuses() {
    return useQuery({
        queryKey: ["decision-statuses"],
        queryFn: getDecisionStatuses,
        staleTime: 10 * 60 * 1000,
    });
}
