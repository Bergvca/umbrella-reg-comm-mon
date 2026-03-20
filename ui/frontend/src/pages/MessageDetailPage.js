import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
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
export function MessageDetailPage() {
    const { index, docId } = useParams();
    const esIndex = index ?? "";
    const esDocId = docId ?? "";
    const { data: message, isLoading, isError } = useMessage(esIndex, esDocId);
    const { data: linkedAlerts } = useAlertsForDocument(esIndex, esDocId);
    const [selectedAlertId, setSelectedAlertId] = useState(null);
    // Auto-select the first alert when data arrives
    const alerts = linkedAlerts ?? [];
    const activeAlertId = selectedAlertId ?? (alerts.length > 0 ? alerts[0].id : null);
    if (isLoading) {
        return (_jsxs("div", { className: "p-6 space-y-4", children: [_jsx(Skeleton, { className: "h-6 w-48" }), _jsx(Skeleton, { className: "h-64 w-full" })] }));
    }
    if (isError || !message) {
        return (_jsx("div", { className: "p-6", children: _jsx(Card, { children: _jsxs(CardContent, { className: "pt-6 text-center space-y-3", children: [_jsx("p", { className: "text-muted-foreground", children: "Message not found." }), _jsx(Link, { to: "/messages", className: "text-sm text-primary hover:underline", children: "\u2190 Back to Messages" })] }) }) }));
    }
    return (_jsxs("div", { className: "p-6", children: [_jsx("div", { className: "mb-6", children: _jsx(Breadcrumb, { children: _jsxs(BreadcrumbList, { children: [_jsx(BreadcrumbItem, { children: _jsx(BreadcrumbLink, { href: "/messages", children: "Messages" }) }), _jsx(BreadcrumbSeparator, {}), _jsx(BreadcrumbItem, { children: _jsxs(BreadcrumbPage, { children: [message.channel, " / ", esDocId] }) })] }) }) }), _jsxs("div", { className: "flex gap-6 items-start", children: [_jsx("div", { className: "flex-1 min-w-0", children: _jsx(Card, { children: _jsx(CardContent, { className: "pt-6", children: _jsx(MessageDisplay, { message: message, esIndex: esIndex }) }) }) }), alerts.length > 0 && (_jsxs("div", { className: "w-80 shrink-0 sticky top-0 max-h-[calc(100vh-7rem)] overflow-y-auto", children: [alerts.length > 1 && (_jsx(AlertPicker, { alerts: alerts, activeId: activeAlertId, onSelect: setSelectedAlertId })), activeAlertId && (_jsx(AlertDetailPanel, { alertId: activeAlertId }))] }))] })] }));
}
/** Tabs to switch between multiple linked alerts. */
function AlertPicker({ alerts, activeId, onSelect, }) {
    return (_jsxs("div", { className: "space-y-1 mb-4", children: [_jsxs("p", { className: "text-xs font-medium text-muted-foreground mb-2", children: [alerts.length, " linked alert", alerts.length !== 1 ? "s" : ""] }), alerts.map((a) => (_jsxs("button", { onClick: () => onSelect(a.id), className: `w-full flex items-center gap-2 rounded-md border px-3 py-2 text-left text-sm transition-colors ${a.id === activeId
                    ? "border-primary bg-primary/5"
                    : "border-transparent hover:bg-muted/50"}`, children: [_jsx(AlertSeverityBadge, { severity: a.severity }), _jsx("span", { className: "flex-1 truncate text-xs", children: a.name }), _jsx(AlertStatusBadge, { status: a.status })] }, a.id)))] }));
}
/** Fetches full alert details + decisions and renders AlertSidePanel. */
function AlertDetailPanel({ alertId }) {
    const { data: alert, isLoading: loadingAlert } = useAlert(alertId);
    const { data: decisions = [], isLoading: loadingDecisions } = useDecisions(alertId);
    if (loadingAlert || !alert) {
        return (_jsxs("div", { className: "space-y-3", children: [_jsx(Skeleton, { className: "h-32 w-full" }), _jsx(Skeleton, { className: "h-24 w-full" })] }));
    }
    return (_jsx(AlertSidePanel, { alert: alert, decisions: decisions, loadingDecisions: loadingDecisions }));
}
