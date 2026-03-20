import { useCallback, useEffect } from "react";
import { useParams, useSearchParams, Link } from "react-router";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { AlertSidePanel } from "@/components/alerts/AlertSidePanel";
import { MessageDisplay } from "@/components/messages/MessageDisplay";
import { useBatchAlerts } from "@/hooks/useQueues";
import { useAlert } from "@/hooks/useAlerts";
import { useDecisions } from "@/hooks/useDecisions";

export function BatchReviewPage() {
  const { queueId = "", batchId = "" } = useParams<{
    queueId: string;
    batchId: string;
  }>();
  const [searchParams, setSearchParams] = useSearchParams();

  const index = Math.max(0, parseInt(searchParams.get("index") ?? "0", 10) || 0);

  const { data: batchAlerts = [], isLoading: loadingBatch } = useBatchAlerts(queueId, batchId);
  const currentAlertId = batchAlerts[index]?.id ?? "";
  const { data: alert, isLoading: loadingAlert } = useAlert(currentAlertId);
  const { data: decisions = [], isLoading: loadingDecisions } = useDecisions(currentAlertId);

  const total = batchAlerts.length;
  const hasPrev = index > 0;
  const hasNext = index < total - 1;

  const goTo = useCallback(
    (i: number) => setSearchParams({ index: String(i) }, { replace: true }),
    [setSearchParams],
  );

  // Keyboard navigation: j/→ = next, k/← = prev
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      const tag = (e.target as HTMLElement).tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      if ((e.target as HTMLElement).isContentEditable) return;
      if ((e.key === "j" || e.key === "ArrowRight") && hasNext) {
        e.preventDefault();
        goTo(index + 1);
      } else if ((e.key === "k" || e.key === "ArrowLeft") && hasPrev) {
        e.preventDefault();
        goTo(index - 1);
      }
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [index, hasPrev, hasNext, goTo]);

  const backLink = `/queues/${queueId}`;

  if (loadingBatch) {
    return (
      <div className="p-6 space-y-4">
        <Skeleton className="h-6 w-48" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (total === 0) {
    return (
      <div className="p-6">
        <Card>
          <CardContent className="pt-6 text-center space-y-3">
            <p className="text-muted-foreground">This batch has no alerts.</p>
            <Link to={backLink} className="text-sm text-primary hover:underline">
              ← Back to Queue
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-6">
      {/* Top nav bar */}
      <div className="flex items-center justify-between mb-6">
        <Link to={backLink} className="text-sm text-muted-foreground hover:text-foreground">
          ← Back to Queue
        </Link>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={!hasPrev}
            onClick={() => goTo(index - 1)}
            title="Previous alert (k / ←)"
          >
            ←
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={!hasNext}
            onClick={() => goTo(index + 1)}
            title="Next alert (j / →)"
          >
            →
          </Button>
        </div>
      </div>

      {/* Alert detail */}
      {loadingAlert || !alert ? (
        <div className="space-y-4">
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      ) : (
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
              onDecisionSuccess={hasNext ? () => goTo(index + 1) : undefined}
              positionLabel={`${index + 1} of ${total}`}
            />
          </div>
        </div>
      )}
    </div>
  );
}
