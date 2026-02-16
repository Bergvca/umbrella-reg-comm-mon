import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
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
    const { id } = useParams();
    const alertId = id ?? "";
    const { data: alert, isLoading: loadingAlert, isError: alertError, } = useAlert(alertId);
    const { data: decisions = [], isLoading: loadingDecisions } = useDecisions(alertId);
    if (loadingAlert) {
        return (_jsxs("div", { className: "p-6 space-y-4", children: [_jsx(Skeleton, { className: "h-6 w-32" }), _jsx(Skeleton, { className: "h-32 w-full" }), _jsx(Skeleton, { className: "h-64 w-full" })] }));
    }
    if (alertError || !alert) {
        return (_jsx("div", { className: "p-6", children: _jsx(Card, { children: _jsxs(CardContent, { className: "pt-6 text-center space-y-3", children: [_jsx("p", { className: "text-muted-foreground", children: "Alert not found." }), _jsx(Link, { to: "/alerts", className: "text-sm text-primary hover:underline", children: "\u2190 Back to Alerts" })] }) }) }));
    }
    return (_jsxs("div", { className: "p-6 space-y-6 max-w-4xl", children: [_jsx(Link, { to: "/alerts", className: "text-sm text-muted-foreground hover:text-foreground", children: "\u2190 Back to Alerts" }), _jsx(AlertMetadataCard, { alert: alert }), _jsxs(Tabs, { defaultValue: "message", children: [_jsxs(TabsList, { children: [_jsx(TabsTrigger, { value: "message", children: "Message" }), _jsxs(TabsTrigger, { value: "decisions", children: ["Decisions", !loadingDecisions && decisions.length > 0 && (_jsxs("span", { className: "ml-1.5 text-xs", children: ["(", decisions.length, ")"] }))] })] }), _jsx(TabsContent, { value: "message", className: "mt-4", children: alert.message ? (_jsx(MessageDisplay, { message: alert.message, esIndex: alert.es_index })) : (_jsx("p", { className: "text-sm text-muted-foreground", children: "Message not found in Elasticsearch." })) }), _jsx(TabsContent, { value: "decisions", className: "mt-4", children: loadingDecisions ? (_jsx(Skeleton, { className: "h-24 w-full" })) : (_jsx(DecisionTimeline, { decisions: decisions })) })] }), _jsx(DecisionForm, { alertId: alertId, alertStatus: alert.status })] }));
}
