import { useState, useRef, useEffect } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { Participant } from "@/lib/types";

const ROLE_CLASSES: Record<string, string> = {
  from: "text-blue-600 border-blue-300",
  to: "text-gray-600 border-gray-300",
  cc: "text-muted-foreground border-muted",
};

interface Props {
  participants: Participant[];
}

function ParticipantChip({ participant: p }: { participant: Participant }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-sm whitespace-nowrap">
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
    </span>
  );
}

export function ParticipantList({ participants }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [visibleCount, setVisibleCount] = useState(participants.length);
  const containerRef = useRef<HTMLDivElement>(null);
  const measuringRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (expanded) return;

    function measure() {
      const container = containerRef.current;
      const measuring = measuringRef.current;
      if (!container || !measuring) return;

      const containerWidth = container.offsetWidth;
      const children = measuring.children;
      // Reserve space for the "+N" button (~48px)
      const buttonReserve = 48;
      let count = 0;
      let usedWidth = 0;

      for (let i = 0; i < children.length; i++) {
        const child = children[i] as HTMLElement;
        const childWidth = child.offsetWidth + 8; // 8px gap
        if (usedWidth + childWidth > containerWidth - buttonReserve && i > 0) {
          break;
        }
        usedWidth += childWidth;
        count++;
      }

      setVisibleCount(count || 1);
    }

    measure();

    const observer = new ResizeObserver(measure);
    if (containerRef.current) observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [participants, expanded]);

  if (participants.length === 0) {
    return <p className="text-sm text-muted-foreground">No participants.</p>;
  }

  const hiddenCount = expanded ? 0 : participants.length - visibleCount;
  const displayedParticipants = expanded
    ? participants
    : participants.slice(0, visibleCount);

  return (
    <div ref={containerRef} className="relative">
      {/* Hidden measuring container */}
      <div
        ref={measuringRef}
        className="flex flex-wrap items-center gap-2 absolute invisible h-0 overflow-hidden"
        aria-hidden
      >
        {participants.map((p, i) => (
          <ParticipantChip key={i} participant={p} />
        ))}
      </div>

      {/* Visible participants */}
      <div className={`flex items-center gap-2 ${expanded ? "flex-wrap" : "flex-nowrap overflow-hidden"}`}>
        {displayedParticipants.map((p, i) => (
          <ParticipantChip key={i} participant={p} />
        ))}
        {hiddenCount > 0 && (
          <Button
            variant="outline"
            size="sm"
            className="h-6 px-2 text-xs shrink-0"
            onClick={() => setExpanded(true)}
          >
            +{hiddenCount}
          </Button>
        )}
        {expanded && participants.length > 3 && (
          <Button
            variant="ghost"
            size="sm"
            className="h-6 px-2 text-xs shrink-0"
            onClick={() => setExpanded(false)}
          >
            Show less
          </Button>
        )}
      </div>
    </div>
  );
}
