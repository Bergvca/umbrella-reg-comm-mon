import { useQuery } from "@tanstack/react-query";
import { getAuditLog } from "@/api/audit";
import type { AuditLogParams } from "@/api/audit";

export function useAuditLog(params: AuditLogParams = {}) {
  return useQuery({
    queryKey: ["audit-log", params],
    queryFn: () => getAuditLog(params),
  });
}
