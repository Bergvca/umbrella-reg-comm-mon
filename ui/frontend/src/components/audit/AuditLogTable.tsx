import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDateTime } from "@/lib/utils";
import { AuditDetailDialog } from "./AuditDetailDialog";
import type { AuditLogEntry } from "@/lib/types";

interface AuditLogTableProps {
  entries: AuditLogEntry[];
  isLoading: boolean;
}

export function AuditLogTable({ entries, isLoading }: AuditLogTableProps) {
  const [selected, setSelected] = useState<AuditLogEntry | null>(null);

  if (isLoading) return <Skeleton className="h-64 w-full" />;
  if (!entries.length) return <p className="text-sm text-muted-foreground text-center py-8">No audit events found.</p>;

  return (
    <>
      <div className="border rounded-lg divide-y">
        {entries.map((entry) => (
          <div
            key={entry.id}
            className="flex items-center gap-3 p-3 cursor-pointer hover:bg-muted/50 transition-colors"
            onClick={() => setSelected(entry)}
          >
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <Badge variant="outline" className="text-xs">{entry.object_type}</Badge>
                <span className="text-sm font-medium">{entry.action}</span>
              </div>
              <p className="text-xs text-muted-foreground mt-0.5">
                {entry.actor_id ?? "System"} · {formatDateTime(entry.occurred_at)}
              </p>
            </div>
            <span className="text-xs text-muted-foreground shrink-0">#{entry.object_id}</span>
          </div>
        ))}
      </div>
      <AuditDetailDialog entry={selected} onClose={() => setSelected(null)} />
    </>
  );
}
