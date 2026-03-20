import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useRef, useState } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { AlertCircle, Send, Square } from "lucide-react";
import { useAgentStream } from "@/hooks/useAgentStream";
import { LiveStepTrace } from "./LiveStepTrace";
const STATUS_VARIANT = {
    completed: "default",
    running: "secondary",
    failed: "destructive",
    cancelled: "outline",
};
function RunCard({ run, isActive }) {
    return (_jsx(Card, { className: "mb-4", children: _jsxs(CardContent, { className: "pt-4 space-y-3", children: [_jsxs("div", { className: "flex items-start gap-2", children: [_jsx(Badge, { variant: "outline", className: "shrink-0 mt-0.5", children: "You" }), _jsx("p", { className: "text-sm whitespace-pre-wrap", children: run.input })] }), _jsx(LiveStepTrace, { steps: run.steps, isStreaming: isActive }), run.status === "failed" && run.errorMessage && (_jsxs("div", { className: "flex items-start gap-2 rounded-md border border-destructive/50 bg-destructive/10 px-3 py-2 text-destructive", children: [_jsx(AlertCircle, { className: "h-4 w-4 shrink-0 mt-0.5" }), _jsx("p", { className: "text-sm whitespace-pre-wrap", children: run.errorMessage })] })), run.output && (_jsxs("div", { className: "flex items-start gap-2", children: [_jsx(Badge, { variant: STATUS_VARIANT[run.status] ?? "outline", className: "shrink-0 mt-0.5", children: "Agent" }), _jsx("div", { className: "text-sm prose prose-sm max-w-none prose-p:text-foreground prose-headings:text-foreground prose-strong:text-foreground prose-li:text-foreground prose-td:text-foreground prose-th:text-foreground prose-table:w-full prose-table:border-collapse prose-td:border prose-td:border-border prose-td:px-3 prose-td:py-1.5 prose-th:border prose-th:border-border prose-th:px-3 prose-th:py-1.5 prose-th:bg-muted prose-th:font-semibold", children: _jsx(Markdown, { remarkPlugins: [remarkGfm], children: run.output }) })] })), run.status !== "running" && (_jsxs("div", { className: "flex items-center gap-3 text-xs text-muted-foreground border-t pt-2", children: [_jsx(Badge, { variant: STATUS_VARIANT[run.status] ?? "outline", className: "text-xs", children: run.status }), run.durationMs != null && (_jsx("span", { children: run.durationMs < 1000
                                ? `${run.durationMs}ms`
                                : `${(run.durationMs / 1000).toFixed(1)}s` })), run.totalTokens != null && (_jsxs("span", { children: [run.totalTokens.toLocaleString(), " tokens"] })), run.iterations != null && (_jsxs("span", { children: [run.iterations, " steps"] }))] }))] }) }));
}
export function AgentPlayground({ agent }) {
    const { runs, isStreaming, startRun, cancelRun } = useAgentStream(agent.id);
    const [input, setInput] = useState("");
    const scrollRef = useRef(null);
    const textareaRef = useRef(null);
    // Auto-scroll when new content arrives
    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [runs]);
    const handleSubmit = async () => {
        const trimmed = input.trim();
        if (!trimmed || isStreaming)
            return;
        setInput("");
        await startRun(trimmed);
    };
    const handleKeyDown = (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            void handleSubmit();
        }
    };
    // Session totals
    const sessionTokens = runs.reduce((sum, r) => sum + (r.totalTokens ?? 0), 0);
    return (_jsxs("div", { className: "flex flex-col h-[calc(100vh-12rem)]", children: [_jsxs("div", { ref: scrollRef, className: "flex-1 overflow-y-auto p-4 space-y-2", children: [runs.length === 0 && (_jsxs("div", { className: "flex items-center justify-center h-full text-muted-foreground text-sm", children: ["Type a prompt below to test ", _jsx("strong", { className: "mx-1", children: agent.name }), "."] })), runs.map((run, i) => (_jsx(RunCard, { run: run, isActive: i === runs.length - 1 && run.status === "running" }, run.runId)))] }), _jsxs("div", { className: "border-t p-4 space-y-2", children: [_jsxs("div", { className: "flex gap-2", children: [_jsx("textarea", { ref: textareaRef, className: "flex-1 min-h-[2.5rem] max-h-32 rounded-md border bg-background px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-ring", placeholder: `Ask ${agent.name} something...`, value: input, onChange: (e) => setInput(e.target.value), onKeyDown: handleKeyDown, disabled: isStreaming, rows: 1 }), isStreaming ? (_jsx(Button, { variant: "destructive", size: "icon", onClick: () => void cancelRun(), children: _jsx(Square, { className: "h-4 w-4" }) })) : (_jsx(Button, { size: "icon", onClick: () => void handleSubmit(), disabled: !input.trim(), children: _jsx(Send, { className: "h-4 w-4" }) }))] }), _jsxs("div", { className: "flex items-center gap-3 text-xs text-muted-foreground", children: [_jsxs("span", { children: ["Model: ", agent.model.name] }), _jsxs("span", { children: ["Temperature: ", agent.temperature] }), _jsxs("span", { children: ["Max iterations: ", agent.max_iterations] }), runs.length > 0 && (_jsxs("span", { className: "ml-auto", children: ["Session: ", runs.length, " run", runs.length !== 1 ? "s" : "", sessionTokens > 0 && `, ${sessionTokens.toLocaleString()} tokens`] }))] })] })] }));
}
