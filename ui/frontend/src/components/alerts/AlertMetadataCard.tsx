import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AlertSeverityBadge } from "./AlertSeverityBadge";
import { AlertStatusBadge } from "./AlertStatusBadge";
import { formatDateTime } from "@/lib/utils";
import type { AlertWithMessage } from "@/lib/types";

interface Props {
  alert: AlertWithMessage;
}

export function AlertMetadataCard({ alert }: Props) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-4">
          <CardTitle className="text-lg">{alert.name}</CardTitle>
          <AlertSeverityBadge severity={alert.severity} />
        </div>
      </CardHeader>
      <CardContent>
        <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-3">
          <div>
            <dt className="text-muted-foreground">Status</dt>
            <dd className="mt-0.5">
              <AlertStatusBadge status={alert.status} />
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Rule</dt>
            <dd className="mt-0.5 font-medium">{alert.rule_name ?? "—"}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Policy</dt>
            <dd className="mt-0.5 font-medium">{alert.policy_name ?? "—"}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Created</dt>
            <dd className="mt-0.5">{formatDateTime(alert.created_at)}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Message Timestamp</dt>
            <dd className="mt-0.5">
              {alert.es_document_ts ? formatDateTime(alert.es_document_ts) : "—"}
            </dd>
          </div>
        </dl>
      </CardContent>
    </Card>
  );
}
