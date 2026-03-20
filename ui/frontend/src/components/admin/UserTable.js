import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { useUsers } from "@/hooks/useUsers";
import { UserForm } from "./UserForm";
import { UserGroupManager } from "./UserGroupManager";
export function UserTable() {
    const { data: users, isLoading } = useUsers();
    const [editUser, setEditUser] = useState(null);
    const [manageUser, setManageUser] = useState(null);
    const [showAdd, setShowAdd] = useState(false);
    if (isLoading)
        return _jsx(Skeleton, { className: "h-48 w-full" });
    return (_jsxs("div", { className: "space-y-3", children: [_jsx("div", { className: "flex justify-end", children: _jsx(Button, { onClick: () => setShowAdd(true), children: "+ Add User" }) }), _jsxs("div", { className: "border rounded-lg divide-y", children: [!users?.items?.length && (_jsx("p", { className: "p-4 text-sm text-muted-foreground", children: "No users found." })), users?.items?.map((u) => (_jsxs("div", { className: "flex items-center gap-3 p-3", children: [_jsxs("div", { className: "flex-1", children: [_jsx("p", { className: "text-sm font-medium", children: u.full_name ?? u.email }), _jsx("p", { className: "text-xs text-muted-foreground", children: u.email })] }), u.is_active ? (_jsx(Badge, { variant: "outline", className: "text-green-600 border-green-300", children: "Active" })) : (_jsx(Badge, { variant: "outline", className: "text-muted-foreground", children: "Inactive" })), _jsx(Button, { size: "sm", variant: "ghost", onClick: () => setManageUser(u), children: "Groups" }), _jsx(Button, { size: "sm", variant: "outline", onClick: () => setEditUser(u), children: "Edit" })] }, u.id)))] }), _jsx(Dialog, { open: showAdd, onOpenChange: setShowAdd, children: _jsxs(DialogContent, { children: [_jsx(DialogHeader, { children: _jsx(DialogTitle, { children: "New User" }) }), _jsx(UserForm, { onSuccess: () => setShowAdd(false), onCancel: () => setShowAdd(false) })] }) }), _jsx(Dialog, { open: !!editUser, onOpenChange: (o) => !o && setEditUser(null), children: _jsxs(DialogContent, { children: [_jsx(DialogHeader, { children: _jsx(DialogTitle, { children: "Edit User" }) }), editUser && _jsx(UserForm, { user: editUser, onSuccess: () => setEditUser(null), onCancel: () => setEditUser(null) })] }) }), _jsx(Sheet, { open: !!manageUser, onOpenChange: (o) => !o && setManageUser(null), children: _jsxs(SheetContent, { children: [_jsx(SheetHeader, { children: _jsx(SheetTitle, { children: manageUser?.full_name ?? manageUser?.email }) }), _jsx("div", { className: "mt-6", children: manageUser && _jsx(UserGroupManager, { userId: manageUser.id }) })] }) })] }));
}
