import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { useUpdateBatch } from "@/hooks/useQueues";
import { useUsers } from "@/hooks/useUsers";
export function BatchAssignDialog({ queueId, batch }) {
    const [open, setOpen] = useState(false);
    const [assignedTo, setAssignedTo] = useState(batch.assigned_to ?? "unassigned");
    const { data: users } = useUsers();
    const mutation = useUpdateBatch(queueId);
    function handleSubmit(e) {
        e.preventDefault();
        mutation.mutate({ batchId: batch.id, assigned_to: assignedTo === "unassigned" ? undefined : assignedTo }, { onSuccess: () => setOpen(false) });
    }
    return (_jsxs(Dialog, { open: open, onOpenChange: setOpen, children: [_jsx(DialogTrigger, { asChild: true, children: _jsx(Button, { size: "sm", variant: "outline", children: "Assign" }) }), _jsxs(DialogContent, { children: [_jsx(DialogHeader, { children: _jsxs(DialogTitle, { children: ["Assign Batch \u2014 ", batch.name] }) }), _jsxs("form", { onSubmit: handleSubmit, className: "space-y-4", children: [_jsxs("div", { className: "space-y-1", children: [_jsx(Label, { children: "Assign To" }), _jsxs(Select, { value: assignedTo, onValueChange: setAssignedTo, children: [_jsx(SelectTrigger, { children: _jsx(SelectValue, { placeholder: "Unassigned" }) }), _jsxs(SelectContent, { children: [_jsx(SelectItem, { value: "unassigned", children: "Unassigned" }), users?.items?.map((u) => (_jsx(SelectItem, { value: u.id, children: u.full_name ?? u.email }, u.id)))] })] })] }), _jsxs("div", { className: "flex gap-2 justify-end", children: [_jsx(Button, { type: "button", variant: "outline", onClick: () => setOpen(false), children: "Cancel" }), _jsx(Button, { type: "submit", disabled: mutation.isPending, children: mutation.isPending ? "Saving…" : "Save" })] })] })] })] }));
}
