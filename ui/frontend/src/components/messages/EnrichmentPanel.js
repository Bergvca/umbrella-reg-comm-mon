import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Badge } from "@/components/ui/badge";
export function EnrichmentPanel({ message }) {
    const hasAny = message.sentiment ||
        message.risk_score !== undefined ||
        message.matched_policies.length > 0 ||
        message.entities.length > 0;
    if (!hasAny) {
        return (_jsx("p", { className: "text-sm text-muted-foreground", children: "No enrichment data available." }));
    }
    return (_jsxs("div", { className: "space-y-3 text-sm", children: [(message.sentiment || message.risk_score !== undefined) && (_jsxs("div", { className: "flex flex-wrap gap-4", children: [message.sentiment && (_jsxs("div", { children: [_jsx("span", { className: "text-muted-foreground", children: "Sentiment: " }), _jsx("span", { className: "font-medium capitalize", children: message.sentiment }), message.sentiment_score !== undefined && (_jsxs("span", { className: "text-muted-foreground ml-1", children: ["(", message.sentiment_score.toFixed(2), ")"] }))] })), message.risk_score !== undefined && (_jsxs("div", { children: [_jsx("span", { className: "text-muted-foreground", children: "Risk Score: " }), _jsx("span", { className: "font-medium", children: message.risk_score })] }))] })), message.matched_policies.length > 0 && (_jsxs("div", { children: [_jsx("p", { className: "text-muted-foreground mb-1", children: "Matched Policies:" }), _jsx("p", { className: "font-medium", children: message.matched_policies.join(", ") })] })), message.entities.length > 0 && (_jsxs("div", { children: [_jsx("p", { className: "text-muted-foreground mb-1.5", children: "Entities:" }), _jsx("div", { className: "flex flex-wrap gap-1.5", children: message.entities.map((e, i) => (_jsxs(Badge, { variant: "secondary", className: "text-xs", children: [e.label, ": ", e.text] }, i))) })] }))] }));
}
