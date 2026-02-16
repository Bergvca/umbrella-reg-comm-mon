import { Link } from "react-router";
import { AlertSeverityBadge } from "@/components/alerts/AlertSeverityBadge";
import { AlertStatusBadge } from "@/components/alerts/AlertStatusBadge";
import type { AlertOut } from "@/lib/types";

interface LinkedAlertsProps {
  alerts: AlertOut[];
}

export function LinkedAlerts({ alerts }: LinkedAlertsProps) {
  if (!alerts.length) {
    return <p className="text-sm text-muted-foreground">No alerts linked to this message.</p>;
  }

  return (
    <div className="space-y-2">
      {alerts.map((alert) => (
        <Link
          key={alert.id}
          to={`/alerts/${alert.id}`}
          className="flex items-center gap-3 border rounded-lg p-3 hover:bg-muted/50 transition-colors"
        >
          <AlertSeverityBadge severity={alert.severity} />
          <span className="flex-1 text-sm font-medium">{alert.name}</span>
          <AlertStatusBadge status={alert.status} />
        </Link>
      ))}
    </div>
  );
}
