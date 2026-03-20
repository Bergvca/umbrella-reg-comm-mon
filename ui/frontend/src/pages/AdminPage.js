import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { UserTable } from "@/components/admin/UserTable";
import { GroupTable } from "@/components/admin/GroupTable";
import { DecisionStatusTable } from "@/components/admin/DecisionStatusTable";
export function AdminPage() {
    return (_jsxs("div", { className: "p-6 space-y-6 max-w-5xl", children: [_jsx("h1", { className: "text-2xl font-semibold", children: "Administration" }), _jsxs(Tabs, { defaultValue: "users", children: [_jsxs(TabsList, { children: [_jsx(TabsTrigger, { value: "users", children: "Users" }), _jsx(TabsTrigger, { value: "groups", children: "Groups" }), _jsx(TabsTrigger, { value: "queues", children: "Decision Queues" })] }), _jsx(TabsContent, { value: "users", className: "pt-4", children: _jsx(UserTable, {}) }), _jsx(TabsContent, { value: "groups", className: "pt-4", children: _jsx(GroupTable, {}) }), _jsx(TabsContent, { value: "queues", className: "pt-4", children: _jsx(DecisionStatusTable, {}) })] })] }));
}
