import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useParams, Link } from "react-router";
import { Breadcrumb, BreadcrumbItem, BreadcrumbLink, BreadcrumbList, BreadcrumbPage, BreadcrumbSeparator, } from "@/components/ui/breadcrumb";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent } from "@/components/ui/card";
import { useTrade } from "@/hooks/useTrades";
import { useAlertsForDocument } from "@/hooks/useAlerts";
import { AlertSeverityBadge } from "@/components/alerts/AlertSeverityBadge";
import { AlertStatusBadge } from "@/components/alerts/AlertStatusBadge";
import { TradeDisplay } from "@/components/trades/TradeDisplay";
export function TradeDetailPage() {
    const { index, docId } = useParams();
    const esIndex = index ?? "";
    const esDocId = docId ?? "";
    const { data: trade, isLoading, isError } = useTrade(esIndex, esDocId);
    const { data: linkedAlerts } = useAlertsForDocument(esIndex, esDocId);
    const alerts = linkedAlerts ?? [];
    if (isLoading) {
        return (_jsxs("div", { className: "space-y-4", children: [_jsx(Skeleton, { className: "h-6 w-48" }), _jsx(Skeleton, { className: "h-64 w-full" })] }));
    }
    if (isError || !trade) {
        return (_jsx(Card, { children: _jsxs(CardContent, { className: "pt-6 text-center space-y-3", children: [_jsx("p", { className: "text-muted-foreground", children: "Trade not found." }), _jsx(Link, { to: "/trades", className: "text-sm text-primary hover:underline", children: "Back to Trades" })] }) }));
    }
    return (_jsxs("div", { className: "space-y-6 max-w-4xl", children: [_jsx(Breadcrumb, { children: _jsxs(BreadcrumbList, { children: [_jsx(BreadcrumbItem, { children: _jsx(BreadcrumbLink, { href: "/trades", children: "Trades" }) }), _jsx(BreadcrumbSeparator, {}), _jsx(BreadcrumbItem, { children: _jsxs(BreadcrumbPage, { children: [trade.metadata.ticker ?? "Trade", " / ", esDocId] }) })] }) }), _jsxs("div", { className: "flex gap-6 items-start", children: [_jsx("div", { className: "flex-1 min-w-0", children: _jsx(TradeDisplay, { trade: trade }) }), alerts.length > 0 && (_jsxs("div", { className: "w-72 shrink-0 space-y-2", children: [_jsxs("h3", { className: "text-sm font-medium text-muted-foreground", children: [alerts.length, " linked alert", alerts.length !== 1 ? "s" : ""] }), alerts.map((a) => (_jsxs(Link, { to: `/alerts/${a.id}`, className: "block border rounded-md px-3 py-2 hover:bg-muted/50 transition-colors space-y-1", children: [_jsxs("div", { className: "flex items-center gap-2", children: [_jsx(AlertSeverityBadge, { severity: a.severity }), _jsx(AlertStatusBadge, { status: a.status })] }), _jsx("p", { className: "text-xs truncate", children: a.name })] }, a.id)))] }))] })] }));
}
