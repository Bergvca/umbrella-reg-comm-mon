import { useQuery } from "@tanstack/react-query";
import { getAuditLog } from "@/api/audit";
export function useAuditLog(params = {}) {
    return useQuery({
        queryKey: ["audit-log", params],
        queryFn: () => getAuditLog(params),
    });
}
