import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { ScrollArea } from "@/components/ui/scroll-area";
import { formatRelative, formatDateTime } from "@/lib/utils";
export function DecisionTimeline({ decisions }) {
    if (decisions.length === 0) {
        return _jsx("p", { className: "text-sm text-muted-foreground", children: "No decisions yet." });
    }
    const sorted = [...decisions].sort((a, b) => new Date(b.decided_at).getTime() - new Date(a.decided_at).getTime());
    const inner = (_jsx("div", { className: "space-y-4", children: sorted.map((d, i) => (_jsxs("div", { className: "relative pl-6", children: [_jsx("span", { className: "absolute left-0 top-1.5 h-2.5 w-2.5 rounded-full bg-primary" }), i < sorted.length - 1 && (_jsx("span", { className: "absolute left-1 top-4 h-full w-px bg-border" })), _jsxs("div", { className: "flex items-start justify-between gap-2", children: [_jsx("span", { className: "font-medium text-sm", children: d.status_name ?? d.status_id }), _jsx("span", { className: "text-xs text-muted-foreground shrink-0", title: formatDateTime(d.decided_at), children: formatRelative(d.decided_at) })] }), _jsxs("p", { className: "text-xs text-muted-foreground mt-0.5", children: ["Reviewer: ", d.reviewer_id] }), d.comment && (_jsx("p", { className: "text-sm mt-1 text-foreground/80", children: d.comment }))] }, d.id))) }));
    return decisions.length > 5 ? (_jsx(ScrollArea, { className: "h-72", children: inner })) : (inner);
}
