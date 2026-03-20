import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from "react";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { RuleTable } from "./RuleTable";
import { GroupPolicyManager } from "./GroupPolicyManager";
import { PolicyForm } from "./PolicyForm";
export function PolicyDetail({ policy, canEdit }) {
    const [showEdit, setShowEdit] = useState(false);
    return (_jsxs("div", { className: "space-y-4", children: [_jsxs("div", { className: "flex items-start justify-between pb-3 border-b", children: [_jsxs("div", { children: [_jsx("h3", { className: "font-semibold text-lg", children: policy.name }), policy.description && _jsx("p", { className: "text-sm text-muted-foreground mt-1", children: policy.description }), policy.risk_model_id && (_jsxs(Badge, { variant: "secondary", className: "mt-2", children: ["Risk Model #", policy.risk_model_id] }))] }), canEdit && (_jsx(Button, { size: "sm", variant: "outline", onClick: () => setShowEdit(true), children: "Edit Policy" }))] }), _jsxs(Accordion, { type: "multiple", defaultValue: ["rules", "groups"], children: [_jsxs(AccordionItem, { value: "rules", children: [_jsx(AccordionTrigger, { children: "Rules" }), _jsx(AccordionContent, { children: _jsx(RuleTable, { policyId: policy.id, canEdit: canEdit }) })] }), _jsxs(AccordionItem, { value: "groups", children: [_jsx(AccordionTrigger, { children: "Assigned Groups" }), _jsx(AccordionContent, { children: _jsx(GroupPolicyManager, { policyId: policy.id, canEdit: canEdit }) })] })] }), _jsx(Dialog, { open: showEdit, onOpenChange: setShowEdit, children: _jsxs(DialogContent, { children: [_jsx(DialogHeader, { children: _jsx(DialogTitle, { children: "Edit Policy" }) }), _jsx(PolicyForm, { policy: policy, onSuccess: () => setShowEdit(false), onCancel: () => setShowEdit(false) })] }) })] }));
}
