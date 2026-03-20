import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue, } from "@/components/ui/select";
export function EntityForm({ open, onOpenChange, onSubmit, isLoading }) {
    const [displayName, setDisplayName] = useState("");
    const [entityType, setEntityType] = useState("person");
    const [handleType, setHandleType] = useState("email");
    const [handleValue, setHandleValue] = useState("");
    function handleSubmit(e) {
        e.preventDefault();
        const handles = handleValue.trim()
            ? [{ handle_type: handleType, handle_value: handleValue.trim(), is_primary: true }]
            : [];
        onSubmit({ display_name: displayName, entity_type: entityType, handles });
        setDisplayName("");
        setEntityType("person");
        setHandleType("email");
        setHandleValue("");
    }
    return (_jsx(Dialog, { open: open, onOpenChange: onOpenChange, children: _jsxs(DialogContent, { children: [_jsx(DialogHeader, { children: _jsx(DialogTitle, { children: "Create Entity" }) }), _jsxs("form", { onSubmit: handleSubmit, className: "space-y-4", children: [_jsxs("div", { className: "space-y-2", children: [_jsx(Label, { htmlFor: "display_name", children: "Display Name" }), _jsx(Input, { id: "display_name", value: displayName, onChange: (e) => setDisplayName(e.target.value), required: true })] }), _jsxs("div", { className: "space-y-2", children: [_jsx(Label, { htmlFor: "entity_type", children: "Type" }), _jsxs(Select, { value: entityType, onValueChange: setEntityType, children: [_jsx(SelectTrigger, { children: _jsx(SelectValue, {}) }), _jsxs(SelectContent, { children: [_jsx(SelectItem, { value: "person", children: "Person" }), _jsx(SelectItem, { value: "organization", children: "Organization" }), _jsx(SelectItem, { value: "distribution_list", children: "Distribution List" })] })] })] }), _jsxs("div", { className: "space-y-2", children: [_jsx(Label, { htmlFor: "handle_type", children: "Handle Type" }), _jsxs(Select, { value: handleType, onValueChange: setHandleType, children: [_jsx(SelectTrigger, { children: _jsx(SelectValue, {}) }), _jsxs(SelectContent, { children: [_jsx(SelectItem, { value: "email", children: "Email" }), _jsx(SelectItem, { value: "teams_id", children: "Teams ID" }), _jsx(SelectItem, { value: "bloomberg_uuid", children: "Bloomberg UUID" }), _jsx(SelectItem, { value: "turret_extension", children: "Turret Extension" })] })] })] }), _jsxs("div", { className: "space-y-2", children: [_jsx(Label, { htmlFor: "handle_value", children: "Handle Value" }), _jsx(Input, { id: "handle_value", value: handleValue, onChange: (e) => setHandleValue(e.target.value), placeholder: "e.g. jane.smith@acme.com" })] }), _jsxs(DialogFooter, { children: [_jsx(Button, { type: "button", variant: "outline", onClick: () => onOpenChange(false), children: "Cancel" }), _jsx(Button, { type: "submit", disabled: isLoading || !displayName.trim(), children: isLoading ? "Creating..." : "Create" })] })] })] }) }));
}
