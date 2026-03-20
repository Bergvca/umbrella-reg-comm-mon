import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from "react";
import { useParams, useNavigate, Link } from "react-router";
import { toast } from "sonner";
import { useEntity, useEntityMessages, useEntityAlerts, useDeleteEntity, useAddHandle, useRemoveHandle, useAddAttribute, useRemoveAttribute, } from "@/hooks/useEntities";
import { useAuthStore } from "@/stores/auth";
import { hasRole, formatRelative } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue, } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow, } from "@/components/ui/table";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger, } from "@/components/ui/alert-dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { Trash2 } from "lucide-react";
export function EntityDetailPage() {
    const { id } = useParams();
    const navigate = useNavigate();
    const user = useAuthStore((s) => s.user);
    const isAdmin = user ? hasRole(user.roles, "admin") : false;
    const { data: entity, isLoading, isError } = useEntity(id);
    const { data: messagesData, isLoading: messagesLoading } = useEntityMessages(id, { limit: 10 });
    const { data: alertsData, isLoading: alertsLoading } = useEntityAlerts(id);
    const deleteEntity = useDeleteEntity();
    const addHandle = useAddHandle();
    const removeHandle = useRemoveHandle();
    const addAttribute = useAddAttribute();
    const removeAttribute = useRemoveAttribute();
    // Handle form state
    const [handleType, setHandleType] = useState("email");
    const [handleValue, setHandleValue] = useState("");
    // Attribute form state
    const [attrKey, setAttrKey] = useState("");
    const [attrValue, setAttrValue] = useState("");
    if (isLoading) {
        return (_jsxs("div", { className: "p-6 space-y-4", children: [_jsx(Skeleton, { className: "h-8 w-64" }), _jsx(Skeleton, { className: "h-40 w-full" })] }));
    }
    if (isError || !entity) {
        return (_jsx("div", { className: "p-6", children: _jsx(Card, { children: _jsx(CardContent, { className: "pt-6 text-center text-muted-foreground", children: "Entity not found." }) }) }));
    }
    return (_jsxs("div", { className: "p-6 space-y-6", children: [_jsxs("div", { className: "flex items-center justify-between", children: [_jsxs("div", { className: "space-y-1", children: [_jsx("h1", { className: "text-2xl font-semibold", children: entity.display_name }), _jsxs("div", { className: "flex gap-2 items-center text-sm text-muted-foreground", children: [_jsx(Badge, { variant: "secondary", children: entity.entity_type }), _jsxs("span", { children: ["Created ", formatRelative(entity.created_at)] })] })] }), isAdmin && (_jsxs(AlertDialog, { children: [_jsx(AlertDialogTrigger, { asChild: true, children: _jsx(Button, { variant: "destructive", size: "sm", children: "Delete Entity" }) }), _jsxs(AlertDialogContent, { children: [_jsxs(AlertDialogHeader, { children: [_jsx(AlertDialogTitle, { children: "Delete entity?" }), _jsxs(AlertDialogDescription, { children: ["This will permanently delete ", entity.display_name, " and all associated handles and attributes."] })] }), _jsxs(AlertDialogFooter, { children: [_jsx(AlertDialogCancel, { children: "Cancel" }), _jsx(AlertDialogAction, { onClick: () => deleteEntity.mutate(entity.id, {
                                                    onSuccess: () => {
                                                        toast.success("Entity deleted");
                                                        void navigate("/entities");
                                                    },
                                                }), children: "Delete" })] })] })] }))] }), _jsxs(Card, { children: [_jsx(CardHeader, { children: _jsx(CardTitle, { children: "Handles" }) }), _jsxs(CardContent, { className: "space-y-4", children: [_jsxs(Table, { children: [_jsx(TableHeader, { children: _jsxs(TableRow, { children: [_jsx(TableHead, { children: "Type" }), _jsx(TableHead, { children: "Value" }), _jsx(TableHead, { children: "Primary" }), isAdmin && _jsx(TableHead, { className: "w-12" })] }) }), _jsx(TableBody, { children: entity.handles.length === 0 ? (_jsx(TableRow, { children: _jsx(TableCell, { colSpan: isAdmin ? 4 : 3, className: "text-center text-muted-foreground py-4", children: "No handles." }) })) : (entity.handles.map((h) => (_jsxs(TableRow, { children: [_jsx(TableCell, { children: _jsx(Badge, { variant: "outline", children: h.handle_type }) }), _jsx(TableCell, { className: "font-mono text-sm", children: h.handle_value }), _jsx(TableCell, { children: h.is_primary ? "Yes" : "No" }), isAdmin && (_jsx(TableCell, { children: _jsx(Button, { variant: "ghost", size: "icon", onClick: () => removeHandle.mutate({ entityId: entity.id, handleId: h.id }, { onSuccess: () => toast.success("Handle removed") }), children: _jsx(Trash2, { className: "h-4 w-4" }) }) }))] }, h.id)))) })] }), isAdmin && (_jsxs("form", { className: "flex gap-2 items-end", onSubmit: (e) => {
                                    e.preventDefault();
                                    if (!handleValue.trim())
                                        return;
                                    addHandle.mutate({ entityId: entity.id, body: { handle_type: handleType, handle_value: handleValue.trim() } }, {
                                        onSuccess: () => {
                                            setHandleValue("");
                                            toast.success("Handle added");
                                        },
                                        onError: () => toast.error("Failed to add handle"),
                                    });
                                }, children: [_jsxs(Select, { value: handleType, onValueChange: setHandleType, children: [_jsx(SelectTrigger, { className: "w-40", children: _jsx(SelectValue, {}) }), _jsxs(SelectContent, { children: [_jsx(SelectItem, { value: "email", children: "Email" }), _jsx(SelectItem, { value: "teams_id", children: "Teams ID" }), _jsx(SelectItem, { value: "bloomberg_uuid", children: "Bloomberg UUID" }), _jsx(SelectItem, { value: "turret_extension", children: "Turret Extension" })] })] }), _jsx(Input, { placeholder: "Handle value", value: handleValue, onChange: (e) => setHandleValue(e.target.value), className: "flex-1" }), _jsx(Button, { type: "submit", size: "sm", disabled: addHandle.isPending, children: "Add" })] }))] })] }), _jsxs(Card, { children: [_jsx(CardHeader, { children: _jsx(CardTitle, { children: "Attributes" }) }), _jsxs(CardContent, { className: "space-y-4", children: [_jsxs(Table, { children: [_jsx(TableHeader, { children: _jsxs(TableRow, { children: [_jsx(TableHead, { children: "Key" }), _jsx(TableHead, { children: "Value" }), _jsx(TableHead, { children: "Valid From" }), _jsx(TableHead, { children: "Valid To" }), isAdmin && _jsx(TableHead, { className: "w-12" })] }) }), _jsx(TableBody, { children: entity.attributes.length === 0 ? (_jsx(TableRow, { children: _jsx(TableCell, { colSpan: isAdmin ? 5 : 4, className: "text-center text-muted-foreground py-4", children: "No attributes." }) })) : (entity.attributes.map((a) => (_jsxs(TableRow, { children: [_jsx(TableCell, { className: "font-medium", children: a.attr_key }), _jsx(TableCell, { children: a.attr_value }), _jsx(TableCell, { className: "text-sm text-muted-foreground", children: a.valid_from ? formatRelative(a.valid_from) : "—" }), _jsx(TableCell, { className: "text-sm text-muted-foreground", children: a.valid_to ? formatRelative(a.valid_to) : "—" }), isAdmin && (_jsx(TableCell, { children: _jsx(Button, { variant: "ghost", size: "icon", onClick: () => removeAttribute.mutate({ entityId: entity.id, attrId: a.id }, { onSuccess: () => toast.success("Attribute removed") }), children: _jsx(Trash2, { className: "h-4 w-4" }) }) }))] }, a.id)))) })] }), isAdmin && (_jsxs("form", { className: "flex gap-2 items-end", onSubmit: (e) => {
                                    e.preventDefault();
                                    if (!attrKey.trim() || !attrValue.trim())
                                        return;
                                    addAttribute.mutate({ entityId: entity.id, body: { attr_key: attrKey.trim(), attr_value: attrValue.trim() } }, {
                                        onSuccess: () => {
                                            setAttrKey("");
                                            setAttrValue("");
                                            toast.success("Attribute added");
                                        },
                                        onError: () => toast.error("Failed to add attribute"),
                                    });
                                }, children: [_jsxs("div", { className: "space-y-1", children: [_jsx(Label, { className: "text-xs", children: "Key" }), _jsx(Input, { placeholder: "e.g. department", value: attrKey, onChange: (e) => setAttrKey(e.target.value), className: "w-40" })] }), _jsxs("div", { className: "space-y-1 flex-1", children: [_jsx(Label, { className: "text-xs", children: "Value" }), _jsx(Input, { placeholder: "e.g. Trading", value: attrValue, onChange: (e) => setAttrValue(e.target.value) })] }), _jsx(Button, { type: "submit", size: "sm", disabled: addAttribute.isPending, children: "Add" })] }))] })] }), _jsxs(Card, { children: [_jsx(CardHeader, { children: _jsxs(CardTitle, { children: ["Recent Messages", messagesData && messagesData.total > 0 && (_jsxs("span", { className: "ml-2 text-sm font-normal text-muted-foreground", children: ["(", messagesData.total, " total)"] }))] }) }), _jsx(CardContent, { children: messagesLoading ? (_jsx(Skeleton, { className: "h-24 w-full" })) : !messagesData?.items.length ? (_jsx("p", { className: "text-sm text-muted-foreground text-center py-4", children: "No messages found." })) : (_jsxs(Table, { children: [_jsx(TableHeader, { children: _jsxs(TableRow, { children: [_jsx(TableHead, { children: "Timestamp" }), _jsx(TableHead, { children: "Channel" }), _jsx(TableHead, { children: "Subject / Preview" })] }) }), _jsx(TableBody, { children: messagesData.items.map((hit) => (_jsxs(TableRow, { children: [_jsx(TableCell, { className: "text-sm whitespace-nowrap", children: formatRelative(hit.message.timestamp) }), _jsx(TableCell, { children: _jsx(Badge, { variant: "outline", children: hit.message.channel }) }), _jsx(TableCell, { children: _jsx(Link, { to: `/messages/${hit.index}/${hit.message.message_id}`, className: "text-sm hover:underline", children: hit.message.body_text?.slice(0, 100) ?? "—" }) })] }, `${hit.index}/${hit.message.message_id}`))) })] })) })] }), _jsxs(Card, { children: [_jsx(CardHeader, { children: _jsx(CardTitle, { children: "Alerts" }) }), _jsx(CardContent, { children: alertsLoading ? (_jsx(Skeleton, { className: "h-24 w-full" })) : !alertsData?.length ? (_jsx("p", { className: "text-sm text-muted-foreground text-center py-4", children: "No alerts linked." })) : (_jsxs(Table, { children: [_jsx(TableHeader, { children: _jsxs(TableRow, { children: [_jsx(TableHead, { children: "Created" }), _jsx(TableHead, { children: "Rule" }), _jsx(TableHead, { children: "Severity" }), _jsx(TableHead, { children: "Status" })] }) }), _jsx(TableBody, { children: alertsData.map((a) => (_jsxs(TableRow, { children: [_jsx(TableCell, { className: "text-sm whitespace-nowrap", children: formatRelative(a.created_at) }), _jsx(TableCell, { className: "text-sm", children: _jsx(Link, { to: `/messages/${a.es_index}/${a.es_document_id}`, className: "hover:underline", children: a.rule_name ?? a.name }) }), _jsx(TableCell, { children: _jsx(Badge, { variant: "outline", children: a.severity }) }), _jsx(TableCell, { children: _jsx(Badge, { variant: "secondary", children: a.status }) })] }, a.id))) })] })) })] })] }));
}
