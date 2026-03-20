import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useCreateRule, useUpdateRule } from "@/hooks/usePolicies";
export function RuleForm({ policyId, rule, onSuccess, onCancel }) {
    const [name, setName] = useState(rule?.name ?? "");
    const [description, setDescription] = useState(rule?.description ?? "");
    const [severity, setSeverity] = useState(rule?.severity ?? "low");
    const [kql, setKql] = useState(rule?.kql ?? "");
    const createMutation = useCreateRule(policyId);
    const updateMutation = useUpdateRule(policyId);
    const isPending = createMutation.isPending || updateMutation.isPending;
    function handleSubmit(e) {
        e.preventDefault();
        const payload = { name, description: description || undefined, kql, severity };
        if (rule) {
            updateMutation.mutate({ ruleId: rule.id, ...payload }, { onSuccess });
        }
        else {
            createMutation.mutate(payload, { onSuccess });
        }
    }
    return (_jsxs("form", { onSubmit: handleSubmit, className: "space-y-4", children: [_jsxs("div", { className: "space-y-1", children: [_jsx(Label, { children: "Name" }), _jsx(Input, { value: name, onChange: (e) => setName(e.target.value), required: true })] }), _jsxs("div", { className: "space-y-1", children: [_jsx(Label, { children: "Description" }), _jsx(Textarea, { value: description, onChange: (e) => setDescription(e.target.value), rows: 2 })] }), _jsxs("div", { className: "space-y-1", children: [_jsx(Label, { children: "Severity" }), _jsxs(Select, { value: severity, onValueChange: setSeverity, children: [_jsx(SelectTrigger, { children: _jsx(SelectValue, {}) }), _jsxs(SelectContent, { children: [_jsx(SelectItem, { value: "low", children: "Low" }), _jsx(SelectItem, { value: "medium", children: "Medium" }), _jsx(SelectItem, { value: "high", children: "High" }), _jsx(SelectItem, { value: "critical", children: "Critical" })] })] })] }), _jsxs("div", { className: "space-y-1", children: [_jsx(Label, { children: "KQL Expression" }), _jsx(Textarea, { value: kql, onChange: (e) => setKql(e.target.value), rows: 4, className: "font-mono text-sm", placeholder: "e.g. body_text: (insider OR confidential)" })] }), _jsxs("div", { className: "flex gap-2 justify-end", children: [_jsx(Button, { type: "button", variant: "outline", onClick: onCancel, children: "Cancel" }), _jsx(Button, { type: "submit", disabled: isPending, children: isPending ? "Saving…" : "Save" })] })] }));
}
