import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { formatDateTime } from "@/lib/utils";
import type { AuditLogEntry } from "@/lib/types";

interface AuditDetailDialogProps {
  entry: AuditLogEntry | null;
  onClose: () => void;
}

export function AuditDetailDialog({ entry, onClose }: AuditDetailDialogProps) {
  if (!entry) return null;

  return (
    <Dialog open={!!entry} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Audit Entry — {entry.action}</DialogTitle>
        </DialogHeader>
        <div className="space-y-3 text-sm">
          <div className="grid grid-cols-2 gap-2">
            <div>
              <span className="text-muted-foreground">Time:</span>{" "}
              {formatDateTime(entry.occurred_at)}
            </div>
            <div>
              <span className="text-muted-foreground">Actor:</span>{" "}
              {entry.actor_id ?? "System"}
            </div>
            <div>
              <span className="text-muted-foreground">Object:</span>{" "}
              {entry.object_type} #{entry.object_id}
            </div>
            {entry.ip_address && (
              <div>
                <span className="text-muted-foreground">IP:</span> {entry.ip_address}
              </div>
            )}
          </div>
          {entry.old_values && (
            <div>
              <p className="font-medium text-muted-foreground mb-1">Before</p>
              <pre className="bg-muted rounded p-2 text-xs overflow-auto max-h-40">
                {JSON.stringify(entry.old_values, null, 2)}
              </pre>
            </div>
          )}
          {entry.new_values && (
            <div>
              <p className="font-medium text-muted-foreground mb-1">After</p>
              <pre className="bg-muted rounded p-2 text-xs overflow-auto max-h-40">
                {JSON.stringify(entry.new_values, null, 2)}
              </pre>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
