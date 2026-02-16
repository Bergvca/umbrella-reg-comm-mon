import { useSearchParams } from "react-router";
import { AuditFilterBar } from "@/components/audit/AuditFilterBar";
import { AuditLogTable } from "@/components/audit/AuditLogTable";
import { useAuditLog } from "@/hooks/useAuditLog";
import type { AuditLogParams } from "@/api/audit";

export function AuditPage() {
  const [searchParams, setSearchParams] = useSearchParams();

  const params: AuditLogParams = {
    actor_id: searchParams.get("actor_id") ?? undefined,
    object_type: searchParams.get("object_type") ?? undefined,
    date_from: searchParams.get("date_from") ?? undefined,
    date_to: searchParams.get("date_to") ?? undefined,
    offset: Number(searchParams.get("offset") ?? 0),
    limit: 50,
  };

  const { data, isLoading } = useAuditLog(params);

  function updateParams(next: AuditLogParams) {
    const p: Record<string, string> = {};
    if (next.actor_id) p.actor_id = next.actor_id;
    if (next.object_type) p.object_type = next.object_type;
    if (next.date_from) p.date_from = next.date_from;
    if (next.date_to) p.date_to = next.date_to;
    setSearchParams(p);
  }

  return (
    <div className="p-6 space-y-6 max-w-5xl">
      <h1 className="text-2xl font-semibold">Audit Log</h1>
      <AuditFilterBar params={params} onChange={updateParams} />
      <AuditLogTable entries={data?.items ?? []} isLoading={isLoading} />
    </div>
  );
}
