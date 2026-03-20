import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { useCreateQueue } from "@/hooks/useQueues";
import { usePolicies } from "@/hooks/usePolicies";
export function CreateQueueDialog() {
    const [open, setOpen] = useState(false);
    const [name, setName] = useState("");
    const [description, setDescription] = useState("");
    const [policyId, setPolicyId] = useState("");
    const mutation = useCreateQueue();
    const { data: policiesData } = usePolicies();
    function handleSubmit(e) {
        e.preventDefault();
        mutation.mutate({ name, description: description || undefined, policy_id: policyId }, {
            onSuccess: () => {
                setOpen(false);
                setName("");
                setDescription("");
                setPolicyId("");
            },
        });
    }
    return (_jsxs(Dialog, { open: open, onOpenChange: setOpen, children: [_jsx(DialogTrigger, { asChild: true, children: _jsx(Button, { children: "+ New Queue" }) }), _jsxs(DialogContent, { children: [_jsx(DialogHeader, { children: _jsx(DialogTitle, { children: "New Review Queue" }) }), _jsxs("form", { onSubmit: handleSubmit, className: "space-y-4", children: [_jsxs("div", { className: "space-y-1", children: [_jsx(Label, { children: "Name" }), _jsx(Input, { value: name, onChange: (e) => setName(e.target.value), required: true })] }), _jsxs("div", { className: "space-y-1", children: [_jsx(Label, { children: "Description" }), _jsx(Textarea, { value: description, onChange: (e) => setDescription(e.target.value), rows: 2 })] }), _jsxs("div", { className: "space-y-1", children: [_jsx(Label, { children: "Policy" }), _jsxs(Select, { value: policyId, onValueChange: setPolicyId, required: true, children: [_jsx(SelectTrigger, { children: _jsx(SelectValue, { placeholder: "Select a policy" }) }), _jsx(SelectContent, { children: policiesData?.items?.map((p) => (_jsx(SelectItem, { value: p.id, children: p.name }, p.id))) })] })] }), _jsxs("div", { className: "flex gap-2 justify-end", children: [_jsx(Button, { type: "button", variant: "outline", onClick: () => setOpen(false), children: "Cancel" }), _jsx(Button, { type: "submit", disabled: mutation.isPending || !policyId, children: mutation.isPending ? "Creating…" : "Create" })] })] })] })] }));
}
