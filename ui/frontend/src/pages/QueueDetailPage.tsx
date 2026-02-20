import { useParams, Link, useSearchParams } from "react-router";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { AlertTable } from "@/components/alerts/AlertTable";
import { BatchTable } from "@/components/queues/BatchTable";
import { useQueue, useQueueBatches, useGenerateBatches, useBatchAlerts } from "@/hooks/useQueues";
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
  const generateMutation = useGenerateBatches(queueId);
  const { data: batchAlerts, isLoading: loadingAlerts } = useBatchAlerts(queueId, batchId);

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
          {canManage && (
            <Button
              size="sm"
              onClick={() => generateMutation.mutate()}
              disabled={generateMutation.isPending}
            >
              {generateMutation.isPending ? "Generating..." : "Generate Batches"}
            </Button>
          )}
        </div>
        {generateMutation.isError && (
          <p className="text-sm text-destructive">
            {(generateMutation.error as Error)?.message ?? "Failed to generate batches"}
          </p>
        )}
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
          <h2 className="text-base font-semibold mb-3">Batch Alerts</h2>
          <AlertTable
            data={batchAlerts}
            total={batchAlerts?.length ?? 0}
            offset={0}
            limit={50}
            onPageChange={() => {}}
            isLoading={loadingAlerts}
          />
        </div>
      )}
    </div>
  );
}
