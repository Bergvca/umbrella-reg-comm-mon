import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useCreateRiskModel, useUpdateRiskModel } from "@/hooks/useRiskModels";
export function RiskModelForm({ model, onSuccess, onCancel }) {
    const [name, setName] = useState(model?.name ?? "");
    const [description, setDescription] = useState(model?.description ?? "");
    const createMutation = useCreateRiskModel();
    const updateMutation = useUpdateRiskModel();
    const isPending = createMutation.isPending || updateMutation.isPending;
    function handleSubmit(e) {
        e.preventDefault();
        const payload = { name, description: description || undefined };
        if (model) {
            updateMutation.mutate({ id: model.id, ...payload }, { onSuccess });
        }
        else {
            createMutation.mutate(payload, { onSuccess });
        }
    }
    return (_jsxs("form", { onSubmit: handleSubmit, className: "space-y-4", children: [_jsxs("div", { className: "space-y-1", children: [_jsx(Label, { children: "Name" }), _jsx(Input, { value: name, onChange: (e) => setName(e.target.value), required: true })] }), _jsxs("div", { className: "space-y-1", children: [_jsx(Label, { children: "Description" }), _jsx(Textarea, { value: description, onChange: (e) => setDescription(e.target.value), rows: 3 })] }), _jsxs("div", { className: "flex gap-2 justify-end", children: [_jsx(Button, { type: "button", variant: "outline", onClick: onCancel, children: "Cancel" }), _jsx(Button, { type: "submit", disabled: isPending, children: isPending ? "Saving…" : "Save" })] })] }));
}
