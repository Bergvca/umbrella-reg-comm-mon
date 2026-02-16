import { Skeleton } from "@/components/ui/skeleton";
import { BatchCard } from "./BatchCard";
import { useMyQueue } from "@/hooks/useQueues";

export function MyQueueList() {
  const { data: batches, isLoading, isError } = useMyQueue();

  if (isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-24 w-full" />
        ))}
      </div>
    );
  }

  if (isError) {
    return <p className="text-sm text-destructive">Failed to load your queue.</p>;
  }

  if (!batches || batches.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">No batches assigned to you.</p>
    );
  }

  return (
    <div className="space-y-3">
      {batches.map((batch) => (
        <BatchCard key={batch.id} batch={batch} />
      ))}
    </div>
  );
}
