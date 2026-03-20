import { useParams, Link } from "react-router";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent } from "@/components/ui/card";
import { useTrade } from "@/hooks/useTrades";
import { useAlertsForDocument } from "@/hooks/useAlerts";
import { AlertSeverityBadge } from "@/components/alerts/AlertSeverityBadge";
import { AlertStatusBadge } from "@/components/alerts/AlertStatusBadge";
import { TradeDisplay } from "@/components/trades/TradeDisplay";
import type { AlertOut } from "@/lib/types";

export function TradeDetailPage() {
  const { index, docId } = useParams<{ index: string; docId: string }>();
  const esIndex = index ?? "";
  const esDocId = docId ?? "";

  const { data: trade, isLoading, isError } = useTrade(esIndex, esDocId);
  const { data: linkedAlerts } = useAlertsForDocument(esIndex, esDocId);
  const alerts = linkedAlerts ?? [];

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-6 w-48" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (isError || !trade) {
    return (
      <Card>
        <CardContent className="pt-6 text-center space-y-3">
          <p className="text-muted-foreground">Trade not found.</p>
          <Link to="/trades" className="text-sm text-primary hover:underline">
            Back to Trades
          </Link>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6 max-w-4xl">
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbLink href="/trades">Trades</BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>
              {trade.metadata.ticker ?? "Trade"} / {esDocId}
            </BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>

      <div className="flex gap-6 items-start">
        <div className="flex-1 min-w-0">
          <TradeDisplay trade={trade} />
        </div>

        {/* Linked alerts sidebar */}
        {alerts.length > 0 && (
          <div className="w-72 shrink-0 space-y-2">
            <h3 className="text-sm font-medium text-muted-foreground">
              {alerts.length} linked alert{alerts.length !== 1 ? "s" : ""}
            </h3>
            {alerts.map((a: AlertOut) => (
              <Link
                key={a.id}
                to={`/alerts/${a.id}`}
                className="block border rounded-md px-3 py-2 hover:bg-muted/50 transition-colors space-y-1"
              >
                <div className="flex items-center gap-2">
                  <AlertSeverityBadge severity={a.severity} />
                  <AlertStatusBadge status={a.status} />
                </div>
                <p className="text-xs truncate">{a.name}</p>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
