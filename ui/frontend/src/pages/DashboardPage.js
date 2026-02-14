import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useAlertStats } from "@/hooks/useAlerts";
import { StatCard } from "@/components/dashboard/StatCard";
import { AlertsBySeverity } from "@/components/dashboard/AlertsBySeverity";
import { AlertsByChannel } from "@/components/dashboard/AlertsByChannel";
import { AlertsOverTime } from "@/components/dashboard/AlertsOverTime";
import { AlertTriangle, AlertCircle, ShieldAlert, Info } from "lucide-react";
export function DashboardPage() {
    const { data: stats, isLoading, isError } = useAlertStats();
    if (isLoading) {
        return (_jsxs("div", { className: "space-y-6", children: [_jsx("h1", { className: "text-2xl font-semibold", children: "Dashboard" }), _jsx("div", { className: "grid gap-4 sm:grid-cols-2 lg:grid-cols-4", children: Array.from({ length: 4 }).map((_, i) => (_jsx("div", { className: "h-28 animate-pulse rounded-lg bg-muted" }, i))) })] }));
    }
    if (isError || !stats) {
        return (_jsxs("div", { className: "space-y-6", children: [_jsx("h1", { className: "text-2xl font-semibold", children: "Dashboard" }), _jsx("p", { className: "text-destructive", children: "Failed to load dashboard data." })] }));
    }
    const severityCount = (level) => stats.by_severity.find((b) => b.key === level)?.count ?? 0;
    return (_jsxs("div", { className: "space-y-6", children: [_jsx("h1", { className: "text-2xl font-semibold", children: "Dashboard" }), _jsxs("div", { className: "grid gap-4 sm:grid-cols-2 lg:grid-cols-4", children: [_jsx(StatCard, { title: "Total Alerts", value: stats.total, icon: AlertTriangle }), _jsx(StatCard, { title: "Critical", value: severityCount("critical"), icon: ShieldAlert, variant: "critical" }), _jsx(StatCard, { title: "High", value: severityCount("high"), icon: AlertCircle, variant: "high" }), _jsx(StatCard, { title: "Medium / Low", value: severityCount("medium") + severityCount("low"), icon: Info, variant: "medium" })] }), _jsxs("div", { className: "grid gap-6 lg:grid-cols-2", children: [_jsx(AlertsOverTime, { data: stats.over_time }), _jsx(AlertsBySeverity, { data: stats.by_severity })] }), _jsx(AlertsByChannel, { data: stats.by_channel })] }));
}
