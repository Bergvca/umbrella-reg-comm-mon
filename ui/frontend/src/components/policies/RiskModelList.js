import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { useRiskModels } from "@/hooks/useRiskModels";
import { RiskModelForm } from "./RiskModelForm";
export function RiskModelList({ canEdit }) {
    const { data: models, isLoading } = useRiskModels();
    const [showAdd, setShowAdd] = useState(false);
    const [editModel, setEditModel] = useState(null);
    if (isLoading)
        return _jsx(Skeleton, { className: "h-24 w-full" });
    return (_jsxs("div", { className: "space-y-3", children: [canEdit && (_jsx("div", { className: "flex justify-end", children: _jsx(Button, { onClick: () => setShowAdd(true), children: "+ Add Risk Model" }) })), !models?.items?.length && _jsx("p", { className: "text-sm text-muted-foreground", children: "No risk models defined." }), _jsx("div", { className: "space-y-2", children: models?.items?.map((m) => (_jsxs("div", { className: "border rounded-lg p-4 space-y-1", children: [_jsxs("div", { className: "flex items-center justify-between", children: [_jsx("span", { className: "font-medium", children: m.name }), canEdit && (_jsx(Button, { size: "sm", variant: "outline", onClick: () => setEditModel(m), children: "Edit" }))] }), m.description && _jsx("p", { className: "text-sm text-muted-foreground", children: m.description })] }, m.id))) }), _jsx(Dialog, { open: showAdd, onOpenChange: setShowAdd, children: _jsxs(DialogContent, { children: [_jsx(DialogHeader, { children: _jsx(DialogTitle, { children: "New Risk Model" }) }), _jsx(RiskModelForm, { onSuccess: () => setShowAdd(false), onCancel: () => setShowAdd(false) })] }) }), _jsx(Dialog, { open: !!editModel, onOpenChange: (o) => !o && setEditModel(null), children: _jsxs(DialogContent, { children: [_jsx(DialogHeader, { children: _jsx(DialogTitle, { children: "Edit Risk Model" }) }), editModel && (_jsx(RiskModelForm, { model: editModel, onSuccess: () => setEditModel(null), onCancel: () => setEditModel(null) }))] }) })] }));
}
