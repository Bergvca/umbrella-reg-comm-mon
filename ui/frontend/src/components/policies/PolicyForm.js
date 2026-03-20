import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useRiskModels } from "@/hooks/useRiskModels";
import { useCreatePolicy, useUpdatePolicy } from "@/hooks/usePolicies";
export function PolicyForm({ policy, onSuccess, onCancel }) {
    const [name, setName] = useState(policy?.name ?? "");
    const [description, setDescription] = useState(policy?.description ?? "");
    const [riskModelId, setRiskModelId] = useState(policy?.risk_model_id ?? "none");
    const { data: riskModels } = useRiskModels();
    const createMutation = useCreatePolicy();
    const updateMutation = useUpdatePolicy();
    const isPending = createMutation.isPending || updateMutation.isPending;
    function handleSubmit(e) {
        e.preventDefault();
        if (policy) {
            updateMutation.mutate({ id: policy.id, name, description: description || undefined }, { onSuccess });
        }
        else {
            createMutation.mutate({ risk_model_id: riskModelId === "none" ? "" : riskModelId, name, description: description || undefined }, { onSuccess });
        }
    }
    return (_jsxs("form", { onSubmit: handleSubmit, className: "space-y-4", children: [_jsxs("div", { className: "space-y-1", children: [_jsx(Label, { children: "Name" }), _jsx(Input, { value: name, onChange: (e) => setName(e.target.value), required: true })] }), _jsxs("div", { className: "space-y-1", children: [_jsx(Label, { children: "Description" }), _jsx(Textarea, { value: description, onChange: (e) => setDescription(e.target.value), rows: 3 })] }), _jsxs("div", { className: "space-y-1", children: [_jsx(Label, { children: "Risk Model" }), _jsxs(Select, { value: riskModelId, onValueChange: setRiskModelId, children: [_jsx(SelectTrigger, { children: _jsx(SelectValue, { placeholder: "None" }) }), _jsxs(SelectContent, { children: [_jsx(SelectItem, { value: "none", children: "None" }), riskModels?.items?.map((m) => (_jsx(SelectItem, { value: m.id, children: m.name }, m.id)))] })] })] }), _jsxs("div", { className: "flex gap-2 justify-end", children: [_jsx(Button, { type: "button", variant: "outline", onClick: onCancel, children: "Cancel" }), _jsx(Button, { type: "submit", disabled: isPending, children: isPending ? "Saving…" : "Save" })] })] }));
}
