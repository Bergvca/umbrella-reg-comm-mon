import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useState } from "react";
import { buildExportUrl } from "@/api/export";
export function ExportButton({ type, params }) {
    const [format, setFormat] = useState("csv");
    function handleExport() {
        const url = buildExportUrl(type, params, format);
        window.open(url, "_blank");
    }
    return (_jsxs("div", { className: "flex gap-2 items-center", children: [_jsxs(Select, { value: format, onValueChange: (v) => setFormat(v), children: [_jsx(SelectTrigger, { className: "w-24 h-8 text-xs", children: _jsx(SelectValue, {}) }), _jsxs(SelectContent, { children: [_jsx(SelectItem, { value: "csv", children: "CSV" }), _jsx(SelectItem, { value: "json", children: "JSON" })] })] }), _jsx(Button, { size: "sm", variant: "outline", onClick: handleExport, children: "Export" })] }));
}
