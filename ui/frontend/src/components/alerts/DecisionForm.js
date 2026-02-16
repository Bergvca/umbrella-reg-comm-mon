import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue, } from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useDecisionStatuses, useCreateDecision } from "@/hooks/useDecisions";
export function DecisionForm({ alertId, alertStatus, onSuccess }) {
    const [selectedStatusId, setSelectedStatusId] = useState("");
    const [comment, setComment] = useState("");
    const [submitted, setSubmitted] = useState(false);
    const { data: statuses, isLoading: loadingStatuses } = useDecisionStatuses();
    const mutation = useCreateDecision(alertId);
    const isClosed = alertStatus === "closed";
    function handleSubmit(e) {
        e.preventDefault();
        if (!selectedStatusId)
            return;
        mutation.mutate({ status_id: selectedStatusId, comment: comment || undefined }, {
            onSuccess: () => {
                setSelectedStatusId("");
                setComment("");
                setSubmitted(true);
                setTimeout(() => setSubmitted(false), 2000);
                onSuccess?.();
            },
        });
    }
    return (_jsxs(Card, { children: [_jsx(CardHeader, { className: "pb-2", children: _jsx(CardTitle, { className: "text-base", children: "Submit Decision" }) }), _jsx(CardContent, { children: isClosed ? (_jsx("p", { className: "text-sm text-muted-foreground", children: "This alert is closed." })) : (_jsxs("form", { onSubmit: handleSubmit, className: "space-y-4", children: [_jsxs("div", { className: "space-y-1.5", children: [_jsx(Label, { htmlFor: "decision-status", children: "Status" }), _jsxs(Select, { value: selectedStatusId, onValueChange: setSelectedStatusId, disabled: loadingStatuses || mutation.isPending, children: [_jsx(SelectTrigger, { id: "decision-status", children: _jsx(SelectValue, { placeholder: "Select a status\u2026" }) }), _jsx(SelectContent, { children: statuses?.map((s) => (_jsxs(SelectItem, { value: s.id, children: [s.name, s.is_terminal ? " (closes alert)" : ""] }, s.id))) })] })] }), _jsxs("div", { className: "space-y-1.5", children: [_jsx(Label, { htmlFor: "decision-comment", children: "Comment" }), _jsx(Textarea, { id: "decision-comment", placeholder: "Add a comment\u2026", value: comment, onChange: (e) => setComment(e.target.value), disabled: mutation.isPending, rows: 3 })] }), _jsx(Button, { type: "submit", disabled: !selectedStatusId || mutation.isPending, className: "w-full sm:w-auto", children: mutation.isPending ? "Submitting…" : submitted ? "Submitted!" : "Submit Decision" }), mutation.isError && (_jsx("p", { className: "text-sm text-destructive", children: "Failed to submit decision. Please try again." }))] })) })] }));
}
