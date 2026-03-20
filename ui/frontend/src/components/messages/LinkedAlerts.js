import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Link } from "react-router";
import { AlertSeverityBadge } from "@/components/alerts/AlertSeverityBadge";
import { AlertStatusBadge } from "@/components/alerts/AlertStatusBadge";
export function LinkedAlerts({ alerts }) {
    if (!alerts.length) {
        return _jsx("p", { className: "text-sm text-muted-foreground", children: "No alerts linked to this message." });
    }
    return (_jsx("div", { className: "space-y-2", children: alerts.map((alert) => (_jsxs(Link, { to: `/alerts/${alert.id}`, className: "flex items-center gap-3 border rounded-lg p-3 hover:bg-muted/50 transition-colors", children: [_jsx(AlertSeverityBadge, { severity: alert.severity }), _jsxs("div", { className: "flex-1 min-w-0", children: [_jsx("span", { className: "text-sm font-medium block truncate", children: alert.name }), (alert.policy_name || alert.rule_name) && (_jsx("span", { className: "text-xs text-muted-foreground block truncate", children: [alert.policy_name, alert.rule_name].filter(Boolean).join(" → ") }))] }), _jsx(AlertStatusBadge, { status: alert.status })] }, alert.id))) }));
}
