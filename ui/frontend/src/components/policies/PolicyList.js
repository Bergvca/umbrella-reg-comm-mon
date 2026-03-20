import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from "react";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { usePolicies } from "@/hooks/usePolicies";
import { PolicyDetail } from "./PolicyDetail";
import { PolicyForm } from "./PolicyForm";
export function PolicyList({ canEdit }) {
    const { data: policies, isLoading } = usePolicies();
    const [showAdd, setShowAdd] = useState(false);
    if (isLoading)
        return _jsx(Skeleton, { className: "h-32 w-full" });
    return (_jsxs("div", { className: "space-y-4", children: [canEdit && (_jsx("div", { className: "flex justify-end", children: _jsx(Button, { onClick: () => setShowAdd(true), children: "+ Add Policy" }) })), !policies?.items?.length && _jsx("p", { className: "text-sm text-muted-foreground", children: "No policies defined." }), _jsx(Accordion, { type: "single", collapsible: true, className: "space-y-2", children: policies?.items?.map((policy) => (_jsxs(AccordionItem, { value: String(policy.id), className: "border rounded-lg px-4", children: [_jsx(AccordionTrigger, { className: "hover:no-underline", children: _jsx("span", { className: "font-medium", children: policy.name }) }), _jsx(AccordionContent, { children: _jsx(PolicyDetail, { policy: policy, canEdit: canEdit }) })] }, policy.id))) }), _jsx(Dialog, { open: showAdd, onOpenChange: setShowAdd, children: _jsxs(DialogContent, { children: [_jsx(DialogHeader, { children: _jsx(DialogTitle, { children: "New Policy" }) }), _jsx(PolicyForm, { onSuccess: () => setShowAdd(false), onCancel: () => setShowAdd(false) })] }) })] }));
}
