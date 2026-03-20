import { useState } from "react";
import { useParams, Link } from "react-router";
import { Breadcrumb, BreadcrumbItem, BreadcrumbLink, BreadcrumbList, BreadcrumbPage, BreadcrumbSeparator } from "@/components/ui/breadcrumb";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent } from "@/components/ui/card";
import { MessageDisplay } from "@/components/messages/MessageDisplay";
import { AlertSidePanel } from "@/components/alerts/AlertSidePanel";
import { AlertSeverityBadge } from "@/components/alerts/AlertSeverityBadge";
import { AlertStatusBadge } from "@/components/alerts/AlertStatusBadge";
import { useMessage } from "@/hooks/useMessages";
import { useAlertsForDocument } from "@/hooks/useAlerts";
import { useAlert } from "@/hooks/useAlerts";
import { useDecisions } from "@/hooks/useDecisions";
import type { AlertOut } from "@/lib/types";

export function MessageDetailPage() {
  const { index, docId } = useParams<{ index: string; docId: string }>();
  const esIndex = index ?? "";
  const esDocId = docId ?? "";

  const { data: message, isLoading, isError } = useMessage(esIndex, esDocId);
  const { data: linkedAlerts } = useAlertsForDocument(esIndex, esDocId);

  const [selectedAlertId, setSelectedAlertId] = useState<string | null>(null);

  // Auto-select the first alert when data arrives
  const alerts = linkedAlerts ?? [];
  const activeAlertId = selectedAlertId ?? (alerts.length > 0 ? alerts[0].id : null);

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <Skeleton className="h-6 w-48" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (isError || !message) {
    return (
      <div className="p-6">
        <Card>
          <CardContent className="pt-6 text-center space-y-3">
            <p className="text-muted-foreground">Message not found.</p>
            <Link to="/messages" className="text-sm text-primary hover:underline">
              ← Back to Messages
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-6">
      {/* Top nav */}
      <div className="mb-6">
        <Breadcrumb>
          <BreadcrumbList>
            <BreadcrumbItem>
              <BreadcrumbLink href="/messages">Messages</BreadcrumbLink>
            </BreadcrumbItem>
            <BreadcrumbSeparator />
            <BreadcrumbItem>
              <BreadcrumbPage>{message.channel} / {esDocId}</BreadcrumbPage>
            </BreadcrumbItem>
          </BreadcrumbList>
        </Breadcrumb>
      </div>

      {/* Two-column layout: message left, alerts right */}
      <div className="flex gap-6 items-start">
        {/* Left panel: message content */}
        <div className="flex-1 min-w-0">
          <Card>
            <CardContent className="pt-6">
              <MessageDisplay message={message} esIndex={esIndex} />
            </CardContent>
          </Card>
        </div>

        {/* Right panel: linked alerts */}
        {alerts.length > 0 && (
          <div className="w-80 shrink-0 sticky top-0 max-h-[calc(100vh-7rem)] overflow-y-auto">
            {alerts.length > 1 && (
              <AlertPicker
                alerts={alerts}
                activeId={activeAlertId!}
                onSelect={setSelectedAlertId}
              />
            )}
            {activeAlertId && (
              <AlertDetailPanel alertId={activeAlertId} />
            )}
          </div>
        )}
      </div>
    </div>
  );
}

/** Tabs to switch between multiple linked alerts. */
function AlertPicker({
  alerts,
  activeId,
  onSelect,
}: {
  alerts: AlertOut[];
  activeId: string;
  onSelect: (id: string) => void;
}) {
  return (
    <div className="space-y-1 mb-4">
      <p className="text-xs font-medium text-muted-foreground mb-2">
        {alerts.length} linked alert{alerts.length !== 1 ? "s" : ""}
      </p>
      {alerts.map((a) => (
        <button
          key={a.id}
          onClick={() => onSelect(a.id)}
          className={`w-full flex items-center gap-2 rounded-md border px-3 py-2 text-left text-sm transition-colors ${
            a.id === activeId
              ? "border-primary bg-primary/5"
              : "border-transparent hover:bg-muted/50"
          }`}
        >
          <AlertSeverityBadge severity={a.severity} />
          <span className="flex-1 truncate text-xs">{a.name}</span>
          <AlertStatusBadge status={a.status} />
        </button>
      ))}
    </div>
  );
}

/** Fetches full alert details + decisions and renders AlertSidePanel. */
function AlertDetailPanel({ alertId }: { alertId: string }) {
  const { data: alert, isLoading: loadingAlert } = useAlert(alertId);
  const { data: decisions = [], isLoading: loadingDecisions } = useDecisions(alertId);

  if (loadingAlert || !alert) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-24 w-full" />
      </div>
    );
  }

  return (
    <AlertSidePanel
      alert={alert}
      decisions={decisions}
      loadingDecisions={loadingDecisions}
    />
  );
}
