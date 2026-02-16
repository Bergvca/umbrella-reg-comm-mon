import { ScrollArea } from "@/components/ui/scroll-area";
import { formatRelative, formatDateTime } from "@/lib/utils";
import type { DecisionOut } from "@/lib/types";

interface Props {
  decisions: DecisionOut[];
}

export function DecisionTimeline({ decisions }: Props) {
  if (decisions.length === 0) {
    return <p className="text-sm text-muted-foreground">No decisions yet.</p>;
  }

  const sorted = [...decisions].sort(
    (a, b) => new Date(b.decided_at).getTime() - new Date(a.decided_at).getTime(),
  );

  const inner = (
    <div className="space-y-4">
      {sorted.map((d, i) => (
        <div key={d.id} className="relative pl-6">
          {/* dot */}
          <span className="absolute left-0 top-1.5 h-2.5 w-2.5 rounded-full bg-primary" />
          {/* connector line */}
          {i < sorted.length - 1 && (
            <span className="absolute left-1 top-4 h-full w-px bg-border" />
          )}
          <div className="flex items-start justify-between gap-2">
            <span className="font-medium text-sm">{d.status_name ?? d.status_id}</span>
            <span
              className="text-xs text-muted-foreground shrink-0"
              title={formatDateTime(d.decided_at)}
            >
              {formatRelative(d.decided_at)}
            </span>
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">
            Reviewer: {d.reviewer_id}
          </p>
          {d.comment && (
            <p className="text-sm mt-1 text-foreground/80">{d.comment}</p>
          )}
        </div>
      ))}
    </div>
  );

  return decisions.length > 5 ? (
    <ScrollArea className="h-72">{inner}</ScrollArea>
  ) : (
    inner
  );
}
