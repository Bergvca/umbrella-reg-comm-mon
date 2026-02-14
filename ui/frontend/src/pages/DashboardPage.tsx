import { useAlertStats } from "@/hooks/useAlerts";
import { StatCard } from "@/components/dashboard/StatCard";
import { AlertsBySeverity } from "@/components/dashboard/AlertsBySeverity";
import { AlertsByChannel } from "@/components/dashboard/AlertsByChannel";
import { AlertsOverTime } from "@/components/dashboard/AlertsOverTime";
import { AlertTriangle, AlertCircle, ShieldAlert, Info } from "lucide-react";

export function DashboardPage() {
  const { data: stats, isLoading, isError } = useAlertStats();

  if (isLoading) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div
              key={i}
              className="h-28 animate-pulse rounded-lg bg-muted"
            />
          ))}
        </div>
      </div>
    );
  }

  if (isError || !stats) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <p className="text-destructive">Failed to load dashboard data.</p>
      </div>
    );
  }

  const severityCount = (level: string) =>
    stats.by_severity.find((b) => b.key === level)?.count ?? 0;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Dashboard</h1>

      {/* Stat cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Total Alerts"
          value={stats.total}
          icon={AlertTriangle}
        />
        <StatCard
          title="Critical"
          value={severityCount("critical")}
          icon={ShieldAlert}
          variant="critical"
        />
        <StatCard
          title="High"
          value={severityCount("high")}
          icon={AlertCircle}
          variant="high"
        />
        <StatCard
          title="Medium / Low"
          value={severityCount("medium") + severityCount("low")}
          icon={Info}
          variant="medium"
        />
      </div>

      {/* Charts */}
      <div className="grid gap-6 lg:grid-cols-2">
        <AlertsOverTime data={stats.over_time} />
        <AlertsBySeverity data={stats.by_severity} />
      </div>

      <AlertsByChannel data={stats.by_channel} />
    </div>
  );
}
