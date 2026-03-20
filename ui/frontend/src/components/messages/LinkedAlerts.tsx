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
          <div className="flex-1 min-w-0">
            <span className="text-sm font-medium block truncate">{alert.name}</span>
            {(alert.policy_name || alert.rule_name) && (
              <span className="text-xs text-muted-foreground block truncate">
                {[alert.policy_name, alert.rule_name].filter(Boolean).join(" → ")}
              </span>
            )}
          </div>
          <AlertStatusBadge status={alert.status} />
        </Link>
      ))}
    </div>
  );
}
