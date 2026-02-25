import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
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
    const { id } = useParams();
    const alertId = id ?? "";
    const { data: alert, isLoading: loadingAlert, isError: alertError, } = useAlert(alertId);
    const { data: decisions = [], isLoading: loadingDecisions } = useDecisions(alertId);
    const { prevId, nextId, position, total, goToPrev, goToNext } = useAlertNavigation(alertId);
    if (loadingAlert) {
        return (_jsxs("div", { className: "p-6 space-y-4", children: [_jsx(Skeleton, { className: "h-6 w-32" }), _jsx(Skeleton, { className: "h-32 w-full" }), _jsx(Skeleton, { className: "h-64 w-full" })] }));
    }
    if (alertError || !alert) {
        return (_jsx("div", { className: "p-6", children: _jsx(Card, { children: _jsxs(CardContent, { className: "pt-6 text-center space-y-3", children: [_jsx("p", { className: "text-muted-foreground", children: "Alert not found." }), _jsx(Link, { to: "/alerts", className: "text-sm text-primary hover:underline", children: "\u2190 Back to Alerts" })] }) }) }));
    }
    const positionLabel = position != null && total != null ? `${position} of ${total}` : undefined;
    return (_jsxs("div", { className: "p-6", children: [_jsxs("div", { className: "flex items-center justify-between mb-6", children: [_jsx(Link, { to: "/alerts", className: "text-sm text-muted-foreground hover:text-foreground", children: "\u2190 Back to Alerts" }), position != null && total != null && (_jsxs("div", { className: "flex items-center gap-2", children: [_jsx(Button, { variant: "outline", size: "sm", disabled: !prevId, onClick: goToPrev, title: "Previous alert (k / \u2190)", children: "\u2190" }), _jsx(Button, { variant: "outline", size: "sm", disabled: !nextId, onClick: goToNext, title: "Next alert (j / \u2192)", children: "\u2192" })] }))] }), _jsxs("div", { className: "flex gap-6 items-start", children: [_jsx("div", { className: "flex-1 min-w-0", children: alert.message ? (_jsx(Card, { children: _jsx(CardContent, { className: "pt-6", children: _jsx(MessageDisplay, { message: alert.message, esIndex: alert.es_index }) }) })) : (_jsx(Card, { children: _jsx(CardContent, { className: "pt-6", children: _jsx("p", { className: "text-sm text-muted-foreground", children: "Message not found in Elasticsearch." }) }) })) }), _jsx("div", { className: "w-80 shrink-0 sticky top-0 max-h-[calc(100vh-7rem)] overflow-y-auto", children: _jsx(AlertSidePanel, { alert: alert, decisions: decisions, loadingDecisions: loadingDecisions, positionLabel: positionLabel }) })] })] }));
}
