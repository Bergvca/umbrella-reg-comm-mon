import { useParams, Link } from "react-router";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { AlertSidePanel } from "@/components/alerts/AlertSidePanel";
import { MessageDisplay } from "@/components/messages/MessageDisplay";
import { useAlert } from "@/hooks/useAlerts";
import { useDecisions } from "@/hooks/useDecisions";
import { useAlertNavigation } from "@/hooks/useAlertNavigation";

export function AlertDetailPage() {
  const { id } = useParams<{ id: string }>();
  const alertId = id ?? "";

  const {
    data: alert,
    isLoading: loadingAlert,
    isError: alertError,
  } = useAlert(alertId);

  const { data: decisions = [], isLoading: loadingDecisions } =
    useDecisions(alertId);

  const { prevId, nextId, position, total, goToPrev, goToNext } =
    useAlertNavigation(alertId);

  if (loadingAlert) {
    return (
      <div className="p-6 space-y-4">
        <Skeleton className="h-6 w-32" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (alertError || !alert) {
    return (
      <div className="p-6">
        <Card>
          <CardContent className="pt-6 text-center space-y-3">
            <p className="text-muted-foreground">Alert not found.</p>
            <Link to="/alerts" className="text-sm text-primary hover:underline">
              ← Back to Alerts
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  const positionLabel =
    position != null && total != null ? `${position} of ${total}` : undefined;

  return (
    <div className="p-6">
      {/* Top nav bar */}
      <div className="flex items-center justify-between mb-6">
        <Link to="/alerts" className="text-sm text-muted-foreground hover:text-foreground">
          ← Back to Alerts
        </Link>
        {position != null && total != null && (
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={!prevId}
              onClick={goToPrev}
              title="Previous alert (k / ←)"
            >
              ←
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={!nextId}
              onClick={goToNext}
              title="Next alert (j / →)"
            >
              →
            </Button>
          </div>
        )}
      </div>

      {/* Two-column layout: message left, metadata/decisions right */}
      <div className="flex gap-6 items-start">
        {/* Left panel: message content */}
        <div className="flex-1 min-w-0">
          {alert.message ? (
            <Card>
              <CardContent className="pt-6">
                <MessageDisplay message={alert.message} esIndex={alert.es_index} />
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent className="pt-6">
                <p className="text-sm text-muted-foreground">
                  Message not found in Elasticsearch.
                </p>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Right panel: alert metadata, decisions, submit */}
        <div className="w-80 shrink-0 sticky top-0 max-h-[calc(100vh-7rem)] overflow-y-auto">
          <AlertSidePanel
            alert={alert}
            decisions={decisions}
            loadingDecisions={loadingDecisions}
            positionLabel={positionLabel}
          />
        </div>
      </div>
    </div>
  );
}
