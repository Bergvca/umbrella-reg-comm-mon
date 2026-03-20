import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { useGroups } from "@/hooks/useGroups";
import { GroupForm } from "./GroupForm";
import { GroupDetailPanel } from "./GroupDetailPanel";
export function GroupTable() {
    const { data: groups, isLoading } = useGroups();
    const [showAdd, setShowAdd] = useState(false);
    const [editGroup, setEditGroup] = useState(null);
    const [detailGroup, setDetailGroup] = useState(null);
    if (isLoading)
        return _jsx(Skeleton, { className: "h-48 w-full" });
    return (_jsxs("div", { className: "space-y-3", children: [_jsx("div", { className: "flex justify-end", children: _jsx(Button, { onClick: () => setShowAdd(true), children: "+ Add Group" }) }), _jsxs("div", { className: "border rounded-lg divide-y", children: [!groups?.items?.length && _jsx("p", { className: "p-4 text-sm text-muted-foreground", children: "No groups found." }), groups?.items?.map((g) => (_jsxs("div", { className: "flex items-center gap-3 p-3", children: [_jsxs("div", { className: "flex-1", children: [_jsx("p", { className: "text-sm font-medium", children: g.name }), g.description && _jsx("p", { className: "text-xs text-muted-foreground", children: g.description })] }), _jsx(Button, { size: "sm", variant: "ghost", onClick: () => setDetailGroup(g), children: "Manage" }), _jsx(Button, { size: "sm", variant: "outline", onClick: () => setEditGroup(g), children: "Edit" })] }, g.id)))] }), _jsx(Dialog, { open: showAdd, onOpenChange: setShowAdd, children: _jsxs(DialogContent, { children: [_jsx(DialogHeader, { children: _jsx(DialogTitle, { children: "New Group" }) }), _jsx(GroupForm, { onSuccess: () => setShowAdd(false), onCancel: () => setShowAdd(false) })] }) }), _jsx(Dialog, { open: !!editGroup, onOpenChange: (o) => !o && setEditGroup(null), children: _jsxs(DialogContent, { children: [_jsx(DialogHeader, { children: _jsx(DialogTitle, { children: "Edit Group" }) }), editGroup && _jsx(GroupForm, { group: editGroup, onSuccess: () => setEditGroup(null), onCancel: () => setEditGroup(null) })] }) }), _jsx(Sheet, { open: !!detailGroup, onOpenChange: (o) => !o && setDetailGroup(null), children: _jsxs(SheetContent, { children: [_jsx(SheetHeader, { children: _jsx(SheetTitle, { children: detailGroup?.name }) }), _jsx("div", { className: "mt-6", children: detailGroup && _jsx(GroupDetailPanel, { group: detailGroup }) })] }) })] }));
}
