import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { useCreateBatch } from "@/hooks/useQueues";
export function CreateBatchDialog({ queueId }) {
    const [open, setOpen] = useState(false);
    const [name, setName] = useState("");
    const mutation = useCreateBatch(queueId);
    function handleSubmit(e) {
        e.preventDefault();
        mutation.mutate({ name }, {
            onSuccess: () => {
                setOpen(false);
                setName("");
            },
        });
    }
    return (_jsxs(Dialog, { open: open, onOpenChange: setOpen, children: [_jsx(DialogTrigger, { asChild: true, children: _jsx(Button, { size: "sm", children: "+ New Batch" }) }), _jsxs(DialogContent, { children: [_jsx(DialogHeader, { children: _jsx(DialogTitle, { children: "New Batch" }) }), _jsxs("form", { onSubmit: handleSubmit, className: "space-y-4", children: [_jsxs("div", { className: "space-y-1", children: [_jsx(Label, { children: "Batch Name" }), _jsx(Input, { value: name, onChange: (e) => setName(e.target.value), required: true })] }), _jsxs("div", { className: "flex gap-2 justify-end", children: [_jsx(Button, { type: "button", variant: "outline", onClick: () => setOpen(false), children: "Cancel" }), _jsx(Button, { type: "submit", disabled: mutation.isPending, children: mutation.isPending ? "Creating…" : "Create" })] })] })] })] }));
}
