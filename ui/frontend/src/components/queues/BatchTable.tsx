import { Badge } from "@/components/ui/badge";
import { BatchAssignDialog } from "./BatchAssignDialog";
import { AddItemDialog } from "./AddItemDialog";
import { formatDateTime } from "@/lib/utils";
import type { BatchOut } from "@/lib/types";

interface BatchTableProps {
  queueId: string;
  batches: BatchOut[];
  canManage: boolean;
}

export function BatchTable({ queueId, batches, canManage }: BatchTableProps) {
  if (!batches.length) {
    return <p className="text-sm text-muted-foreground">No batches yet.</p>;
  }

  return (
    <div className="space-y-3">
      {batches.map((batch) => (
        <div key={batch.id} className="border rounded-lg p-4 space-y-2">
          <div className="flex items-center gap-3">
            <span className="font-medium text-sm flex-1">{batch.name}</span>
            <Badge variant={batch.status === "in_progress" ? "default" : batch.status === "completed" ? "secondary" : "outline"}>
              {batch.status}
            </Badge>
            {canManage && <BatchAssignDialog queueId={queueId} batch={batch} />}
            {canManage && <AddItemDialog queueId={queueId} batchId={batch.id} />}
          </div>
          {batch.assigned_to && (
            <p className="text-xs text-muted-foreground">Assigned to: {batch.assigned_to}</p>
          )}
          {batch.created_at && (
            <p className="text-xs text-muted-foreground">Created: {formatDateTime(batch.created_at)}</p>
          )}
          {batch.item_count != null && (
            <p className="text-xs text-muted-foreground">{batch.item_count} items</p>
          )}
        </div>
      ))}
    </div>
  );
}
