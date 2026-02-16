import { Link } from "react-router";
import { Skeleton } from "@/components/ui/skeleton";
import { formatRelative } from "@/lib/utils";
import { useBatchItems } from "@/hooks/useQueues";

interface Props {
  queueId: string;
  batchId: string;
}

export function BatchItemList({ queueId, batchId }: Props) {
  const { data: items, isLoading, isError } = useBatchItems(queueId, batchId);

  if (isLoading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-8 w-full" />
        ))}
      </div>
    );
  }

  if (isError) {
    return <p className="text-sm text-destructive">Failed to load batch items.</p>;
  }

  if (!items || items.length === 0) {
    return <p className="text-sm text-muted-foreground">No items in this batch.</p>;
  }

  return (
    <ol className="space-y-1">
      {items.map((item) => (
        <li
          key={item.id}
          className="flex items-center gap-3 text-sm py-1.5 border-b last:border-0"
        >
          <span className="text-muted-foreground w-6 text-right shrink-0">
            {item.position}.
          </span>
          <Link
            to={`/alerts/${item.alert_id}`}
            className="font-mono text-xs text-primary hover:underline truncate"
          >
            {item.alert_id}
          </Link>
          <span className="text-muted-foreground text-xs ml-auto shrink-0">
            {formatRelative(item.created_at)}
          </span>
        </li>
      ))}
    </ol>
  );
}
