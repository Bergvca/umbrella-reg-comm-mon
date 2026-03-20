import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useState } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow, } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { ChevronDown, ChevronRight, Loader2 } from "lucide-react";
import { useAgentRuns, useAgentRun } from "@/hooks/useAgents";
import { RunStepInspector } from "./RunStepInspector";
import { formatRelative } from "@/lib/utils";
const STATUS_VARIANT = {
    completed: "default",
    running: "secondary",
    pending: "outline",
    failed: "destructive",
    cancelled: "outline",
};
function durationLabel(ms) {
    if (ms == null)
        return "—";
    if (ms < 1000)
        return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
}
function inputSnippet(input) {
    const prompt = input.prompt ?? input.input ?? Object.values(input)[0] ?? "";
    const str = String(prompt);
    return str.length > 80 ? str.slice(0, 80) + "…" : str;
}
function outputSnippet(output) {
    if (!output)
        return "";
    const response = output.response ?? output.output ?? Object.values(output)[0] ?? "";
    return String(response);
}
function totalTokens(usage) {
    if (!usage)
        return "—";
    const total = usage.total_tokens ?? usage.total ?? null;
    return total != null ? String(total) : "—";
}
const PROSE_CLASSES = "prose prose-sm max-w-none prose-p:text-foreground prose-headings:text-foreground prose-strong:text-foreground prose-li:text-foreground prose-td:text-foreground prose-th:text-foreground prose-table:w-full prose-table:border-collapse prose-td:border prose-td:border-border prose-td:px-3 prose-td:py-1.5 prose-th:border prose-th:border-border prose-th:px-3 prose-th:py-1.5 prose-th:bg-muted prose-th:font-semibold";
function ExpandedRunDetail({ runId, run }) {
    const { data: fullRun, isLoading } = useAgentRun(runId);
    const detail = fullRun ?? run;
    const steps = detail.steps;
    return (_jsxs("div", { className: "space-y-3", children: [detail.output && (_jsxs("div", { children: [_jsx("p", { className: "text-xs font-medium text-muted-foreground mb-1", children: "Output" }), _jsx("div", { className: "bg-background rounded border p-3 max-h-96 overflow-auto", children: _jsx("div", { className: PROSE_CLASSES, children: _jsx(Markdown, { remarkPlugins: [remarkGfm], children: outputSnippet(detail.output) }) }) })] })), detail.error_message && (_jsxs("div", { children: [_jsx("p", { className: "text-xs font-medium text-destructive mb-1", children: "Error" }), _jsx("pre", { className: "text-sm whitespace-pre-wrap bg-background rounded border border-destructive/30 p-3 max-h-40 overflow-auto text-destructive", children: detail.error_message })] })), isLoading ? (_jsxs("div", { className: "flex items-center gap-2 text-sm text-muted-foreground py-2", children: [_jsx(Loader2, { className: "h-4 w-4 animate-spin" }), "Loading steps\u2026"] })) : steps && steps.length > 0 ? (_jsx(RunStepInspector, { steps: steps })) : (_jsx("p", { className: "text-sm text-muted-foreground", children: "No step details available." }))] }));
}
export function RunHistory({ agentId }) {
    const { data, isLoading } = useAgentRuns({ agent_id: agentId, limit: 20 });
    const [expandedRunId, setExpandedRunId] = useState(null);
    const headers = (_jsxs(TableRow, { children: [_jsx(TableHead, { className: "w-8" }), _jsx(TableHead, { children: "Status" }), _jsx(TableHead, { children: "Input" }), _jsx(TableHead, { children: "Duration" }), _jsx(TableHead, { children: "Tokens" }), _jsx(TableHead, { children: "Started" })] }));
    if (isLoading) {
        return (_jsx("div", { className: "rounded-md border", children: _jsxs(Table, { children: [_jsx(TableHeader, { children: headers }), _jsx(TableBody, { children: Array.from({ length: 3 }).map((_, i) => (_jsxs(TableRow, { children: [_jsx(TableCell, { children: _jsx(Skeleton, { className: "h-4 w-4" }) }), _jsx(TableCell, { children: _jsx(Skeleton, { className: "h-5 w-20" }) }), _jsx(TableCell, { children: _jsx(Skeleton, { className: "h-5 w-48" }) }), _jsx(TableCell, { children: _jsx(Skeleton, { className: "h-5 w-16" }) }), _jsx(TableCell, { children: _jsx(Skeleton, { className: "h-5 w-12" }) }), _jsx(TableCell, { children: _jsx(Skeleton, { className: "h-5 w-24" }) })] }, i))) })] }) }));
    }
    if (!data || data.items.length === 0) {
        return (_jsx("div", { className: "rounded-md border", children: _jsxs(Table, { children: [_jsx(TableHeader, { children: headers }), _jsx(TableBody, { children: _jsx(TableRow, { children: _jsx(TableCell, { colSpan: 6, className: "text-center py-8 text-muted-foreground", children: "No runs yet." }) }) })] }) }));
    }
    return (_jsx("div", { className: "rounded-md border", children: _jsxs(Table, { children: [_jsx(TableHeader, { children: headers }), _jsx(TableBody, { children: data.items.map((run) => (_jsxs(_Fragment, { children: [_jsxs(TableRow, { className: "cursor-pointer hover:bg-muted/50", onClick: () => setExpandedRunId((prev) => (prev === run.id ? null : run.id)), children: [_jsx(TableCell, { children: _jsx(Button, { variant: "ghost", size: "icon", className: "h-6 w-6", children: expandedRunId === run.id ? (_jsx(ChevronDown, { className: "h-4 w-4" })) : (_jsx(ChevronRight, { className: "h-4 w-4" })) }) }), _jsx(TableCell, { children: _jsx(Badge, { variant: STATUS_VARIANT[run.status] ?? "outline", children: run.status }) }), _jsx(TableCell, { className: "text-sm text-muted-foreground max-w-xs truncate", children: inputSnippet(run.input) }), _jsx(TableCell, { className: "text-sm text-muted-foreground", children: durationLabel(run.duration_ms) }), _jsx(TableCell, { className: "text-sm text-muted-foreground", children: totalTokens(run.token_usage) }), _jsx(TableCell, { className: "text-sm text-muted-foreground", children: formatRelative(run.created_at) })] }, run.id), expandedRunId === run.id && (_jsx(TableRow, { children: _jsx(TableCell, { colSpan: 6, className: "bg-muted/30 px-4 py-3 space-y-3", children: _jsx(ExpandedRunDetail, { runId: run.id, run: run }) }) }, `${run.id}-steps`))] }))) })] }) }));
}
