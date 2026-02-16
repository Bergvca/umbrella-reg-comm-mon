import { useSearchParams } from "react-router";
import { AlertFilters } from "@/components/alerts/AlertFilters";
import { AlertTable } from "@/components/alerts/AlertTable";
import { ExportButton } from "@/components/export/ExportButton";
import { useAlerts } from "@/hooks/useAlerts";
import { useAuthStore } from "@/stores/auth";
import { hasRole } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

const LIMIT = 50;

export function AlertsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const user = useAuthStore((s) => s.user);
  const isSupervisor = user ? hasRole(user.roles, "supervisor") : false;

  const severity = searchParams.get("severity") ?? undefined;
  const status = searchParams.get("status") ?? undefined;
  const offset = Number(searchParams.get("offset") ?? 0);

  const filters = { severity, status };

  const { data, isLoading, isError, refetch } = useAlerts({
    severity,
    status,
    offset,
    limit: LIMIT,
  });

  function handleFiltersChange(next: { severity?: string; status?: string }) {
    const params: Record<string, string> = {};
    if (next.severity) params.severity = next.severity;
    if (next.status) params.status = next.status;
    // reset pagination on filter change
    setSearchParams(params);
  }

  function handlePageChange(newOffset: number) {
    const params: Record<string, string> = {};
    if (severity) params.severity = severity;
    if (status) params.status = status;
    if (newOffset > 0) params.offset = String(newOffset);
    setSearchParams(params);
  }

  if (isError) {
    return (
      <div className="p-6">
        <Card>
          <CardContent className="pt-6 text-center space-y-3">
            <p className="text-muted-foreground">Failed to load alerts.</p>
            <Button variant="outline" onClick={() => void refetch()}>
              Retry
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Alerts</h1>
        {isSupervisor && (
          <ExportButton
            type="alerts"
            params={Object.fromEntries(
              Object.entries({ severity, status }).filter(([, v]) => v != null) as [string, string][]
            )}
          />
        )}
      </div>
      <AlertFilters filters={filters} onChange={handleFiltersChange} />
      <AlertTable
        data={data?.items}
        total={data?.total}
        offset={offset}
        limit={LIMIT}
        onPageChange={handlePageChange}
        isLoading={isLoading}
      />
    </div>
  );
}
