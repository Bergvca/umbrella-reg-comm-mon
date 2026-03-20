import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog";
import { useRules, useDeleteRule } from "@/hooks/usePolicies";
import { RuleForm } from "./RuleForm";
export function RuleTable({ policyId, canEdit }) {
    const { data: rulesData, isLoading } = useRules(policyId);
    const rules = rulesData?.items;
    const deleteMutation = useDeleteRule(policyId);
    const [editRule, setEditRule] = useState(null);
    const [showAdd, setShowAdd] = useState(false);
    if (isLoading)
        return _jsx("p", { className: "text-sm text-muted-foreground", children: "Loading rules\u2026" });
    if (!rules?.length && !canEdit)
        return _jsx("p", { className: "text-sm text-muted-foreground", children: "No rules defined." });
    return (_jsxs("div", { className: "space-y-2", children: [rules?.map((rule) => (_jsxs("div", { className: "flex items-center gap-3 border rounded p-3 text-sm", children: [_jsx(Badge, { variant: "outline", children: rule.severity }), _jsx("span", { className: "flex-1 font-medium", children: rule.name }), rule.description && _jsx("span", { className: "text-muted-foreground text-xs", children: rule.description }), canEdit && (_jsxs("div", { className: "flex gap-1", children: [_jsx(Button, { size: "sm", variant: "ghost", onClick: () => setEditRule(rule), children: "Edit" }), _jsxs(AlertDialog, { children: [_jsx(AlertDialogTrigger, { asChild: true, children: _jsx(Button, { size: "sm", variant: "ghost", className: "text-destructive hover:text-destructive", children: "Delete" }) }), _jsxs(AlertDialogContent, { children: [_jsxs(AlertDialogHeader, { children: [_jsx(AlertDialogTitle, { children: "Delete rule?" }), _jsx(AlertDialogDescription, { children: "This cannot be undone." })] }), _jsxs(AlertDialogFooter, { children: [_jsx(AlertDialogCancel, { children: "Cancel" }), _jsx(AlertDialogAction, { onClick: () => deleteMutation.mutate(rule.id), children: "Delete" })] })] })] })] }))] }, rule.id))), canEdit && (_jsx(Button, { size: "sm", variant: "outline", onClick: () => setShowAdd(true), children: "+ Add Rule" })), _jsx(Dialog, { open: showAdd, onOpenChange: setShowAdd, children: _jsxs(DialogContent, { children: [_jsx(DialogHeader, { children: _jsx(DialogTitle, { children: "Add Rule" }) }), _jsx(RuleForm, { policyId: policyId, onSuccess: () => setShowAdd(false), onCancel: () => setShowAdd(false) })] }) }), _jsx(Dialog, { open: !!editRule, onOpenChange: (o) => !o && setEditRule(null), children: _jsxs(DialogContent, { children: [_jsx(DialogHeader, { children: _jsx(DialogTitle, { children: "Edit Rule" }) }), editRule && (_jsx(RuleForm, { policyId: policyId, rule: editRule, onSuccess: () => setEditRule(null), onCancel: () => setEditRule(null) }))] }) })] }));
}
