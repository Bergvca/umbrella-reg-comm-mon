import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger, } from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
const STEP_TYPE_VARIANT = {
    llm: "default",
    tool: "secondary",
    tool_result: "outline",
};
export function RunStepInspector({ steps }) {
    if (steps.length === 0) {
        return (_jsx("p", { className: "text-sm text-muted-foreground py-2", children: "No steps recorded." }));
    }
    return (_jsx(Accordion, { type: "multiple", className: "w-full", children: steps.map((step) => (_jsxs(AccordionItem, { value: step.id, children: [_jsx(AccordionTrigger, { className: "text-sm hover:no-underline", children: _jsxs("div", { className: "flex items-center gap-3 text-left", children: [_jsxs("span", { className: "text-muted-foreground tabular-nums w-6", children: [step.step_order + 1, "."] }), _jsx(Badge, { variant: STEP_TYPE_VARIANT[step.step_type] ?? "outline", className: "text-xs", children: step.step_type }), step.tool_name && (_jsx("span", { className: "font-mono text-xs text-muted-foreground", children: step.tool_name })), step.duration_ms != null && (_jsxs("span", { className: "ml-auto text-xs text-muted-foreground pr-2", children: [step.duration_ms, "ms"] }))] }) }), _jsx(AccordionContent, { children: _jsxs("div", { className: "space-y-3 pl-9 pb-2", children: [_jsxs("div", { children: [_jsx("p", { className: "text-xs font-medium text-muted-foreground mb-1", children: "Input" }), _jsx("pre", { className: "text-xs bg-muted rounded p-2 overflow-auto max-h-40", children: JSON.stringify(step.input, null, 2) })] }), step.output != null && (_jsxs("div", { children: [_jsx("p", { className: "text-xs font-medium text-muted-foreground mb-1", children: "Output" }), _jsx("pre", { className: "text-xs bg-muted rounded p-2 overflow-auto max-h-40", children: JSON.stringify(step.output, null, 2) })] })), step.token_usage != null && (_jsxs("div", { children: [_jsx("p", { className: "text-xs font-medium text-muted-foreground mb-1", children: "Tokens" }), _jsx("pre", { className: "text-xs bg-muted rounded p-2 overflow-auto", children: JSON.stringify(step.token_usage, null, 2) })] }))] }) })] }, step.id))) }));
}
