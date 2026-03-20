import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useCallback, useEffect } from "react";
import { useParams, useSearchParams, Link } from "react-router";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { AlertSidePanel } from "@/components/alerts/AlertSidePanel";
import { MessageDisplay } from "@/components/messages/MessageDisplay";
import { useBatchAlerts } from "@/hooks/useQueues";
import { useAlert } from "@/hooks/useAlerts";
import { useDecisions } from "@/hooks/useDecisions";
export function BatchReviewPage() {
    const { queueId = "", batchId = "" } = useParams();
    const [searchParams, setSearchParams] = useSearchParams();
    const index = Math.max(0, parseInt(searchParams.get("index") ?? "0", 10) || 0);
    const { data: batchAlerts = [], isLoading: loadingBatch } = useBatchAlerts(queueId, batchId);
    const currentAlertId = batchAlerts[index]?.id ?? "";
    const { data: alert, isLoading: loadingAlert } = useAlert(currentAlertId);
    const { data: decisions = [], isLoading: loadingDecisions } = useDecisions(currentAlertId);
    const total = batchAlerts.length;
    const hasPrev = index > 0;
    const hasNext = index < total - 1;
    const goTo = useCallback((i) => setSearchParams({ index: String(i) }, { replace: true }), [setSearchParams]);
    // Keyboard navigation: j/→ = next, k/← = prev
    useEffect(() => {
        function handleKeyDown(e) {
            const tag = e.target.tagName;
            if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT")
                return;
            if (e.target.isContentEditable)
                return;
            if ((e.key === "j" || e.key === "ArrowRight") && hasNext) {
                e.preventDefault();
                goTo(index + 1);
            }
            else if ((e.key === "k" || e.key === "ArrowLeft") && hasPrev) {
                e.preventDefault();
                goTo(index - 1);
            }
        }
        document.addEventListener("keydown", handleKeyDown);
        return () => document.removeEventListener("keydown", handleKeyDown);
    }, [index, hasPrev, hasNext, goTo]);
    const backLink = `/queues/${queueId}`;
    if (loadingBatch) {
        return (_jsxs("div", { className: "p-6 space-y-4", children: [_jsx(Skeleton, { className: "h-6 w-48" }), _jsx(Skeleton, { className: "h-32 w-full" }), _jsx(Skeleton, { className: "h-64 w-full" })] }));
    }
    if (total === 0) {
        return (_jsx("div", { className: "p-6", children: _jsx(Card, { children: _jsxs(CardContent, { className: "pt-6 text-center space-y-3", children: [_jsx("p", { className: "text-muted-foreground", children: "This batch has no alerts." }), _jsx(Link, { to: backLink, className: "text-sm text-primary hover:underline", children: "\u2190 Back to Queue" })] }) }) }));
    }
    return (_jsxs("div", { className: "p-6", children: [_jsxs("div", { className: "flex items-center justify-between mb-6", children: [_jsx(Link, { to: backLink, className: "text-sm text-muted-foreground hover:text-foreground", children: "\u2190 Back to Queue" }), _jsxs("div", { className: "flex items-center gap-2", children: [_jsx(Button, { variant: "outline", size: "sm", disabled: !hasPrev, onClick: () => goTo(index - 1), title: "Previous alert (k / \u2190)", children: "\u2190" }), _jsx(Button, { variant: "outline", size: "sm", disabled: !hasNext, onClick: () => goTo(index + 1), title: "Next alert (j / \u2192)", children: "\u2192" })] })] }), loadingAlert || !alert ? (_jsxs("div", { className: "space-y-4", children: [_jsx(Skeleton, { className: "h-32 w-full" }), _jsx(Skeleton, { className: "h-64 w-full" })] })) : (_jsxs("div", { className: "flex gap-6 items-start", children: [_jsx("div", { className: "flex-1 min-w-0", children: alert.message ? (_jsx(Card, { children: _jsx(CardContent, { className: "pt-6", children: _jsx(MessageDisplay, { message: alert.message, esIndex: alert.es_index }) }) })) : (_jsx(Card, { children: _jsx(CardContent, { className: "pt-6", children: _jsx("p", { className: "text-sm text-muted-foreground", children: "Message not found in Elasticsearch." }) }) })) }), _jsx("div", { className: "w-80 shrink-0 sticky top-0 max-h-[calc(100vh-7rem)] overflow-y-auto", children: _jsx(AlertSidePanel, { alert: alert, decisions: decisions, loadingDecisions: loadingDecisions, onDecisionSuccess: hasNext ? () => goTo(index + 1) : undefined, positionLabel: `${index + 1} of ${total}` }) })] }))] }));
}
