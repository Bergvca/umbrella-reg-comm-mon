import { Badge } from "@/components/ui/badge";
import type { Participant } from "@/lib/types";

const ROLE_CLASSES: Record<string, string> = {
  from: "text-blue-600 border-blue-300",
  to: "text-gray-600 border-gray-300",
  cc: "text-muted-foreground border-muted",
};

interface Props {
  participants: Participant[];
}

export function ParticipantList({ participants }: Props) {
  if (participants.length === 0) {
    return <p className="text-sm text-muted-foreground">No participants.</p>;
  }

  return (
    <ul className="space-y-1">
      {participants.map((p, i) => (
        <li key={i} className="flex items-center gap-2 text-sm">
          <Badge
            variant="outline"
            className={`text-xs ${ROLE_CLASSES[p.role] ?? "text-muted-foreground"}`}
          >
            {p.role}
          </Badge>
          <span className="font-medium">{p.name}</span>
          {p.id && p.id !== p.name && (
            <span className="text-muted-foreground">({p.id})</span>
          )}
        </li>
      ))}
    </ul>
  );
}
