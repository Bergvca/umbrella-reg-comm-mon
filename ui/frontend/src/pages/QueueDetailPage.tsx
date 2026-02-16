import { useParams, Link, useSearchParams } from "react-router";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent } from "@/components/ui/card";
import { BatchItemList } from "@/components/queues/BatchItemList";
import { BatchTable } from "@/components/queues/BatchTable";
import { CreateBatchDialog } from "@/components/queues/CreateBatchDialog";
import { useQueue, useQueueBatches } from "@/hooks/useQueues";
import { useAuthStore } from "@/stores/auth";
import { hasRole } from "@/lib/utils";

export function QueueDetailPage() {
  const { id } = useParams<{ id: string }>();
  const queueId = id ?? "";
  const [searchParams] = useSearchParams();
  const batchId = searchParams.get("batch") ?? "";

  const user = useAuthStore((s) => s.user);
  const canManage = user ? hasRole(user.roles, "supervisor") : false;

  const { data: queue, isLoading, isError } = useQueue(queueId);
  const { data: batches, isLoading: loadingBatches } = useQueueBatches(queueId);

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <Skeleton className="h-6 w-32" />
        <Skeleton className="h-24 w-full" />
      </div>
    );
  }

  if (isError || !queue) {
    return (
      <div className="p-6">
        <Card>
          <CardContent className="pt-6 text-center space-y-3">
            <p className="text-muted-foreground">Queue not found.</p>
            <Link to="/queues" className="text-sm text-primary hover:underline">
              Back to Queues
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6 max-w-3xl">
      <Link to="/queues" className="text-sm text-muted-foreground hover:text-foreground">
        Back to Queues
      </Link>

      <div>
        <h1 className="text-2xl font-semibold">{queue.name}</h1>
        {queue.description && (
          <p className="text-muted-foreground mt-1">{queue.description}</p>
        )}
      </div>

      <dl className="flex gap-6 text-sm">
        <div>
          <dt className="text-muted-foreground">Batches</dt>
          <dd className="font-medium">{queue.batch_count}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Total Items</dt>
          <dd className="font-medium">{queue.total_items}</dd>
        </div>
      </dl>

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold">Batches</h2>
          {canManage && <CreateBatchDialog queueId={queueId} />}
        </div>
        {loadingBatches ? (
          <div className="space-y-2">
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-16 w-full" />
          </div>
        ) : (
          <BatchTable
            queueId={queueId}
            batches={batches ?? []}
            canManage={canManage}
          />
        )}
      </div>

      {batchId && (
        <div>
          <h2 className="text-base font-semibold mb-3">Batch Items</h2>
          <BatchItemList queueId={queueId} batchId={batchId} />
        </div>
      )}
    </div>
  );
}
