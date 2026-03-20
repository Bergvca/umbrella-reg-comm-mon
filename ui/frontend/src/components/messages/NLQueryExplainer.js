import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from "react";
import { ChevronDown, ChevronRight, Info } from "lucide-react";
import { Button } from "@/components/ui/button";
export function NLQueryExplainer({ explanation, generatedQuery }) {
    const [showQuery, setShowQuery] = useState(false);
    return (_jsxs("div", { className: "rounded-md border border-blue-200 bg-blue-50 p-3 space-y-2", children: [_jsxs("div", { className: "flex items-start gap-2", children: [_jsx(Info, { className: "h-4 w-4 text-blue-600 mt-0.5 shrink-0" }), _jsx("p", { className: "text-sm text-blue-800", children: explanation || "Query translated by AI." })] }), _jsxs("div", { children: [_jsxs(Button, { variant: "ghost", size: "sm", className: "h-6 px-2 text-xs text-blue-700 hover:text-blue-900 hover:bg-blue-100", onClick: () => setShowQuery((v) => !v), children: [showQuery ? (_jsx(ChevronDown, { className: "h-3 w-3 mr-1" })) : (_jsx(ChevronRight, { className: "h-3 w-3 mr-1" })), showQuery ? "Hide" : "View", " generated query"] }), showQuery && (_jsx("pre", { className: "mt-2 text-xs bg-white border border-blue-200 rounded p-2 overflow-auto max-h-48", children: JSON.stringify(generatedQuery, null, 2) }))] })] }));
}
