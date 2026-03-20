import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription, } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
export function BatchUploadDialog({ open, onOpenChange, onUploadCsv, isLoading, result }) {
    const [file, setFile] = useState(null);
    function handleSubmit(e) {
        e.preventDefault();
        if (file)
            onUploadCsv(file);
    }
    return (_jsx(Dialog, { open: open, onOpenChange: onOpenChange, children: _jsxs(DialogContent, { children: [_jsxs(DialogHeader, { children: [_jsx(DialogTitle, { children: "Batch Upload Entities" }), _jsx(DialogDescription, { children: "Upload a CSV file with columns: display_name, entity_type, handle_type, handle_value, is_primary. Additional columns are treated as attributes." })] }), _jsxs("form", { onSubmit: handleSubmit, className: "space-y-4", children: [_jsxs("div", { className: "space-y-2", children: [_jsx(Label, { htmlFor: "csv_file", children: "CSV File" }), _jsx(Input, { id: "csv_file", type: "file", accept: ".csv", onChange: (e) => setFile(e.target.files?.[0] ?? null) })] }), result && (_jsxs("div", { className: "rounded-md border p-3 text-sm space-y-1", children: [_jsxs("p", { children: ["Created: ", result.created] }), _jsxs("p", { children: ["Updated: ", result.updated] }), result.errors.length > 0 && (_jsxs("div", { className: "text-destructive", children: [_jsx("p", { children: "Errors:" }), _jsx("ul", { className: "list-disc pl-4", children: result.errors.map((err, i) => (_jsx("li", { children: err }, i))) })] }))] })), _jsxs(DialogFooter, { children: [_jsx(Button, { type: "button", variant: "outline", onClick: () => onOpenChange(false), children: "Close" }), _jsx(Button, { type: "submit", disabled: isLoading || !file, children: isLoading ? "Uploading..." : "Upload" })] })] })] }) }));
}
