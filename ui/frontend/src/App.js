import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Routes, Route, Navigate, Outlet } from "react-router";
import { useAuthStore } from "@/stores/auth";
import { AppShell } from "@/components/layout/AppShell";
import { LoginPage } from "@/pages/LoginPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { NotFoundPage } from "@/pages/NotFoundPage";
/** Redirects to /login if not authenticated */
function RequireAuth() {
    const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
    if (!isAuthenticated)
        return _jsx(Navigate, { to: "/login", replace: true });
    return _jsx(Outlet, {});
}
/** Redirects to / if already authenticated */
function GuestOnly() {
    const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
    if (isAuthenticated)
        return _jsx(Navigate, { to: "/", replace: true });
    return _jsx(Outlet, {});
}
/** Temporary placeholder for routes not yet implemented */
function ComingSoon({ label }) {
    return (_jsx("div", { className: "flex items-center justify-center h-full", children: _jsxs("p", { className: "text-muted-foreground text-lg", children: [label, " \u2014 coming in Phase 5"] }) }));
}
export function App() {
    return (_jsxs(Routes, { children: [_jsx(Route, { element: _jsx(GuestOnly, {}), children: _jsx(Route, { path: "/login", element: _jsx(LoginPage, {}) }) }), _jsx(Route, { element: _jsx(RequireAuth, {}), children: _jsxs(Route, { element: _jsx(AppShell, {}), children: [_jsx(Route, { index: true, element: _jsx(DashboardPage, {}) }), _jsx(Route, { path: "/alerts", element: _jsx(ComingSoon, { label: "Alerts" }) }), _jsx(Route, { path: "/alerts/:id", element: _jsx(ComingSoon, { label: "Alert Detail" }) }), _jsx(Route, { path: "/messages", element: _jsx(ComingSoon, { label: "Messages" }) }), _jsx(Route, { path: "/queues", element: _jsx(ComingSoon, { label: "Queues" }) }), _jsx(Route, { path: "/policies", element: _jsx(ComingSoon, { label: "Policies" }) }), _jsx(Route, { path: "/admin", element: _jsx(ComingSoon, { label: "Admin" }) }), _jsx(Route, { path: "/audit", element: _jsx(ComingSoon, { label: "Audit Log" }) })] }) }), _jsx(Route, { path: "*", element: _jsx(NotFoundPage, {}) })] }));
}
