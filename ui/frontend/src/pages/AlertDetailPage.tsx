import { useParams, Link } from "react-router";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent } from "@/components/ui/card";
import { AlertMetadataCard } from "@/components/alerts/AlertMetadataCard";
import { DecisionForm } from "@/components/alerts/DecisionForm";
import { DecisionTimeline } from "@/components/alerts/DecisionTimeline";
import { MessageDisplay } from "@/components/messages/MessageDisplay";
import { useAlert } from "@/hooks/useAlerts";
import { useDecisions } from "@/hooks/useDecisions";

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

  return (
    <div className="p-6 space-y-6 max-w-4xl">
      <Link to="/alerts" className="text-sm text-muted-foreground hover:text-foreground">
        ← Back to Alerts
      </Link>

      <AlertMetadataCard alert={alert} />

      <Tabs defaultValue="message">
        <TabsList>
          <TabsTrigger value="message">Message</TabsTrigger>
          <TabsTrigger value="decisions">
            Decisions
            {!loadingDecisions && decisions.length > 0 && (
              <span className="ml-1.5 text-xs">({decisions.length})</span>
            )}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="message" className="mt-4">
          {alert.message ? (
            <MessageDisplay message={alert.message} esIndex={alert.es_index} />
          ) : (
            <p className="text-sm text-muted-foreground">
              Message not found in Elasticsearch.
            </p>
          )}
        </TabsContent>

        <TabsContent value="decisions" className="mt-4">
          {loadingDecisions ? (
            <Skeleton className="h-24 w-full" />
          ) : (
            <DecisionTimeline decisions={decisions} />
          )}
        </TabsContent>
      </Tabs>

      <DecisionForm alertId={alertId} alertStatus={alert.status} />
    </div>
  );
}
