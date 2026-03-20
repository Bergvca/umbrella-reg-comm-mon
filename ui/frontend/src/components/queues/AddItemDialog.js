import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { useAddItemToBatch } from "@/hooks/useQueues";
export function AddItemDialog({ queueId, batchId }) {
    const [open, setOpen] = useState(false);
    const [alertId, setAlertId] = useState("");
    const [position, setPosition] = useState("0");
    const mutation = useAddItemToBatch(queueId, batchId);
    function handleSubmit(e) {
        e.preventDefault();
        mutation.mutate({ alert_id: alertId, position: parseInt(position, 10) }, {
            onSuccess: () => {
                setOpen(false);
                setAlertId("");
                setPosition("0");
            },
        });
    }
    return (_jsxs(Dialog, { open: open, onOpenChange: setOpen, children: [_jsx(DialogTrigger, { asChild: true, children: _jsx(Button, { size: "sm", variant: "ghost", children: "+ Add Item" }) }), _jsxs(DialogContent, { children: [_jsx(DialogHeader, { children: _jsx(DialogTitle, { children: "Add Item to Batch" }) }), _jsxs("form", { onSubmit: handleSubmit, className: "space-y-4", children: [_jsxs("div", { className: "space-y-1", children: [_jsx(Label, { children: "Alert ID" }), _jsx(Input, { value: alertId, onChange: (e) => setAlertId(e.target.value), required: true, placeholder: "Alert ID" })] }), _jsxs("div", { className: "space-y-1", children: [_jsx(Label, { children: "Position" }), _jsx(Input, { type: "number", min: 0, value: position, onChange: (e) => setPosition(e.target.value), required: true })] }), _jsxs("div", { className: "flex gap-2 justify-end", children: [_jsx(Button, { type: "button", variant: "outline", onClick: () => setOpen(false), children: "Cancel" }), _jsx(Button, { type: "submit", disabled: mutation.isPending, children: mutation.isPending ? "Adding…" : "Add" })] })] })] })] }));
}
