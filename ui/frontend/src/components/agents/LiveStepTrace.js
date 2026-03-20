import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ChevronDown, ChevronRight, Loader2, Check, AlertCircle } from "lucide-react";
const TYPE_LABEL = {
    llm_call: "LLM",
    tool_call: "Tool",
    tool_result: "Result",
    tool_error: "Error",
};
const TYPE_VARIANT = {
    llm_call: "default",
    tool_call: "secondary",
    tool_result: "outline",
    tool_error: "destructive",
};
function toolInputSummary(input) {
    if (!input)
        return "";
    const ti = input.tool_input;
    if (typeof ti === "string") {
        return ti.length > 100 ? ti.slice(0, 100) + "\u2026" : ti;
    }
    const str = JSON.stringify(input);
    return str.length > 100 ? str.slice(0, 100) + "\u2026" : str;
}
export function LiveStepTrace({ steps, isStreaming }) {
    const [expanded, setExpanded] = useState(new Set());
    if (steps.length === 0 && isStreaming) {
        return (_jsxs("div", { className: "flex items-center gap-2 py-2 text-sm text-muted-foreground", children: [_jsx(Loader2, { className: "h-4 w-4 animate-spin" }), "Starting agent..."] }));
    }
    if (steps.length === 0)
        return null;
    const toggle = (order) => {
        setExpanded((prev) => {
            const next = new Set(prev);
            if (next.has(order))
                next.delete(order);
            else
                next.add(order);
            return next;
        });
    };
    return (_jsx("div", { className: "space-y-1", children: steps.map((step) => {
            const isExpanded = expanded.has(step.stepOrder);
            const isRunning = step.status === "running";
            const isError = step.type === "tool_error";
            return (_jsxs("div", { className: "rounded border bg-background animate-in slide-in-from-top-1 duration-200", children: [_jsxs("button", { className: "flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-muted/50 transition-colors", onClick: () => toggle(step.stepOrder), children: [isRunning ? (_jsx(Loader2, { className: "h-3.5 w-3.5 animate-spin text-muted-foreground shrink-0" })) : isError ? (_jsx(AlertCircle, { className: "h-3.5 w-3.5 text-destructive shrink-0" })) : (_jsx(Check, { className: "h-3.5 w-3.5 text-green-600 shrink-0" })), _jsx(Badge, { variant: TYPE_VARIANT[step.type] ?? "outline", className: "text-xs shrink-0", children: TYPE_LABEL[step.type] ?? step.type }), step.toolName && (_jsx("span", { className: "font-mono text-xs text-muted-foreground", children: step.toolName })), step.type === "llm_call" && isRunning && (_jsx("span", { className: "text-xs text-muted-foreground", children: "Thinking..." })), step.type === "tool_call" && step.input && (_jsx("span", { className: "text-xs text-muted-foreground truncate max-w-md", children: toolInputSummary(step.input) })), _jsxs("span", { className: "ml-auto flex items-center gap-2", children: [step.durationMs != null && (_jsx("span", { className: "text-xs text-muted-foreground tabular-nums", children: step.durationMs < 1000
                                            ? `${step.durationMs}ms`
                                            : `${(step.durationMs / 1000).toFixed(1)}s` })), _jsx(Button, { variant: "ghost", size: "icon", className: "h-5 w-5 shrink-0", tabIndex: -1, children: isExpanded ? (_jsx(ChevronDown, { className: "h-3 w-3" })) : (_jsx(ChevronRight, { className: "h-3 w-3" })) })] })] }), isExpanded && (_jsxs("div", { className: "border-t px-3 py-2 space-y-2", children: [step.input && (_jsxs("div", { children: [_jsx("p", { className: "text-xs font-medium text-muted-foreground mb-1", children: "Input" }), _jsx("pre", { className: "text-xs bg-muted rounded p-2 overflow-auto max-h-40 whitespace-pre-wrap", children: JSON.stringify(step.input, null, 2) })] })), step.output && (_jsxs("div", { children: [_jsx("p", { className: "text-xs font-medium text-muted-foreground mb-1", children: "Output" }), _jsx("pre", { className: "text-xs bg-muted rounded p-2 overflow-auto max-h-40 whitespace-pre-wrap", children: JSON.stringify(step.output, null, 2) })] })), step.tokenUsage && (_jsxs("div", { children: [_jsx("p", { className: "text-xs font-medium text-muted-foreground mb-1", children: "Tokens" }), _jsx("pre", { className: "text-xs bg-muted rounded p-2 overflow-auto whitespace-pre-wrap", children: JSON.stringify(step.tokenUsage, null, 2) })] }))] }))] }, step.stepOrder));
        }) }));
}
