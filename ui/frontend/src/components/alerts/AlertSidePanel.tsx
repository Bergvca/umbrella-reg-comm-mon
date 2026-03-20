import { Link } from "react-router";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { AlertMetadataCard } from "./AlertMetadataCard";
import { DecisionForm } from "./DecisionForm";
import { DecisionTimeline } from "./DecisionTimeline";
import type { AlertWithMessage, DecisionOut } from "@/lib/types";

interface Props {
  alert: AlertWithMessage;
  decisions: DecisionOut[];
  loadingDecisions: boolean;
  onDecisionSuccess?: () => void;
  /** Queue/batch position info, e.g. "3 of 10" */
  positionLabel?: string;
}

export function AlertSidePanel({
  alert,
  decisions,
  loadingDecisions,
  onDecisionSuccess,
  positionLabel,
}: Props) {
  return (
    <div className="space-y-4">
      {positionLabel && (
        <p className="text-sm text-muted-foreground text-center">
          {positionLabel}
        </p>
      )}

      <AlertMetadataCard alert={alert} />

      {alert.linked_entities?.length > 0 && (
        <div>
          <h3 className="text-sm font-medium mb-2">Linked Entities</h3>
          <div className="flex flex-wrap gap-1.5">
            {alert.linked_entities.map((le) => (
              <Link key={le.entity_id} to={`/entities/${le.entity_id}`}>
                <Badge variant="outline" className="cursor-pointer hover:bg-accent">
                  {le.display_name}
                </Badge>
              </Link>
            ))}
          </div>
        </div>
      )}

      <div>
        <h3 className="text-sm font-medium mb-2">Decision History</h3>
        {loadingDecisions ? (
          <Skeleton className="h-24 w-full" />
        ) : (
          <DecisionTimeline decisions={decisions} />
        )}
      </div>

      <DecisionForm
        alertId={alert.id}
        alertStatus={alert.status}
        onSuccess={onDecisionSuccess}
      />
    </div>
  );
}
