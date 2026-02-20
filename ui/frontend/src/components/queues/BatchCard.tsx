import { useNavigate } from "react-router";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { formatRelative } from "@/lib/utils";
import type { BatchOut, BatchStatus } from "@/lib/types";

const STATUS_CLASSES: Record<BatchStatus, string> = {
  pending: "text-muted-foreground border-muted",
  in_progress: "text-yellow-600 border-yellow-300",
  completed: "text-green-600 border-green-300",
};

interface Props {
  batch: BatchOut;
}

export function BatchCard({ batch }: Props) {
  const navigate = useNavigate();

  return (
    <Card>
      <CardContent className="pt-4 pb-4">
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="font-medium">{batch.name ?? "Unnamed Batch"}</span>
              <Badge variant="outline" className={STATUS_CLASSES[batch.status]}>
                {batch.status.replace("_", " ")}
              </Badge>
            </div>
            <p className="text-sm text-muted-foreground">
              Queue: {batch.queue_id} · Items: {batch.item_count}
            </p>
            {batch.assigned_at && (
              <p className="text-xs text-muted-foreground">
                Assigned {formatRelative(batch.assigned_at)}
              </p>
            )}
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() =>
              void navigate(`/queues/${batch.queue_id}/batches/${batch.id}/review?index=0`)
            }
          >
            Review Batch →
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
