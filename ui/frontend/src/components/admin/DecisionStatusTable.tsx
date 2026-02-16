import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useQueues } from "@/hooks/useQueues";

export function DecisionStatusTable() {
  const { data: queues, isLoading } = useQueues();

  if (isLoading) return <Skeleton className="h-32 w-full" />;

  return (
    <div className="border rounded-lg divide-y">
      {!queues?.items?.length && <p className="p-4 text-sm text-muted-foreground">No queues.</p>}
      {queues?.items?.map((q) => (
        <div key={q.id} className="flex items-center gap-3 p-3">
          <div className="flex-1">
            <p className="text-sm font-medium">{q.name}</p>
            {q.description && <p className="text-xs text-muted-foreground">{q.description}</p>}
          </div>
          <Badge variant="outline">{q.channel}</Badge>
          <Badge variant={q.is_active ? "default" : "secondary"}>
            {q.is_active ? "Active" : "Inactive"}
          </Badge>
        </div>
      ))}
    </div>
  );
}
