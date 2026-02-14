import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { NavLink } from "react-router";
import { LayoutDashboard, AlertTriangle, Search, ListTodo, Shield, Users, FileText, } from "lucide-react";
import { cn, hasRole } from "@/lib/utils";
import { useAuthStore } from "@/stores/auth";
import { Separator } from "@/components/ui/separator";
const NAV_ITEMS = [
    { to: "/", label: "Dashboard", icon: LayoutDashboard, minRole: "reviewer" },
    { to: "/alerts", label: "Alerts", icon: AlertTriangle, minRole: "reviewer" },
    { to: "/messages", label: "Messages", icon: Search, minRole: "reviewer" },
    { to: "/queues", label: "Queues", icon: ListTodo, minRole: "reviewer" },
    { to: "/policies", label: "Policies", icon: Shield, minRole: "admin" },
    { to: "/admin", label: "Users & Groups", icon: Users, minRole: "admin" },
    { to: "/audit", label: "Audit Log", icon: FileText, minRole: "supervisor" },
];
export function Sidebar() {
    const roles = useAuthStore((s) => s.user?.roles ?? []);
    const visibleItems = NAV_ITEMS.filter((item) => hasRole(roles, item.minRole));
    return (_jsxs("aside", { className: "flex w-64 flex-col border-r bg-card", children: [_jsxs("div", { className: "flex h-14 items-center gap-2 px-4 font-semibold", children: [_jsx(Shield, { className: "h-6 w-6 text-brand-600" }), _jsx("span", { className: "text-lg", children: "Umbrella" })] }), _jsx(Separator, {}), _jsx("nav", { className: "flex-1 space-y-1 p-2", children: visibleItems.map((item) => (_jsxs(NavLink, { to: item.to, end: item.to === "/", className: ({ isActive }) => cn("flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors", isActive
                        ? "bg-primary text-primary-foreground"
                        : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"), children: [_jsx(item.icon, { className: "h-4 w-4" }), item.label] }, item.to))) })] }));
}
