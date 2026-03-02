import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Routes, Route, Navigate, Outlet } from "react-router";
import { useAuthStore } from "@/stores/auth";
import { AppShell } from "@/components/layout/AppShell";
import { LoginPage } from "@/pages/LoginPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { AlertsPage } from "@/pages/AlertsPage";
import { AlertDetailPage } from "@/pages/AlertDetailPage";
import { QueuesPage } from "@/pages/QueuesPage";
import { QueueDetailPage } from "@/pages/QueueDetailPage";
import { BatchReviewPage } from "@/pages/BatchReviewPage";
import { MessagesPage } from "@/pages/MessagesPage";
import { MessageDetailPage } from "@/pages/MessageDetailPage";
import { PoliciesPage } from "@/pages/PoliciesPage";
import { EntitiesPage } from "@/pages/EntitiesPage";
import { EntityDetailPage } from "@/pages/EntityDetailPage";
import { AgentsPage } from "@/pages/AgentsPage";
import { AgentDetailPage } from "@/pages/AgentDetailPage";
import { AgentEditorPage } from "@/pages/AgentEditorPage";
import { AgentPlaygroundPage } from "@/pages/AgentPlaygroundPage";
import { AdminPage } from "@/pages/AdminPage";
import { AuditPage } from "@/pages/AuditPage";
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
export function App() {
    return (_jsxs(Routes, { children: [_jsx(Route, { element: _jsx(GuestOnly, {}), children: _jsx(Route, { path: "/login", element: _jsx(LoginPage, {}) }) }), _jsx(Route, { element: _jsx(RequireAuth, {}), children: _jsxs(Route, { element: _jsx(AppShell, {}), children: [_jsx(Route, { index: true, element: _jsx(DashboardPage, {}) }), _jsx(Route, { path: "/alerts", element: _jsx(AlertsPage, {}) }), _jsx(Route, { path: "/alerts/:id", element: _jsx(AlertDetailPage, {}) }), _jsx(Route, { path: "/queues", element: _jsx(QueuesPage, {}) }), _jsx(Route, { path: "/queues/:id", element: _jsx(QueueDetailPage, {}) }), _jsx(Route, { path: "/queues/:queueId/batches/:batchId/review", element: _jsx(BatchReviewPage, {}) }), _jsx(Route, { path: "/messages", element: _jsx(MessagesPage, {}) }), _jsx(Route, { path: "/messages/:index/:docId", element: _jsx(MessageDetailPage, {}) }), _jsx(Route, { path: "/policies", element: _jsx(PoliciesPage, {}) }), _jsx(Route, { path: "/entities", element: _jsx(EntitiesPage, {}) }), _jsx(Route, { path: "/entities/:id", element: _jsx(EntityDetailPage, {}) }), _jsx(Route, { path: "/agents", element: _jsx(AgentsPage, {}) }), _jsx(Route, { path: "/agents/new", element: _jsx(AgentEditorPage, {}) }), _jsx(Route, { path: "/agents/:id", element: _jsx(AgentDetailPage, {}) }), _jsx(Route, { path: "/agents/:id/edit", element: _jsx(AgentEditorPage, {}) }), _jsx(Route, { path: "/agents/:id/playground", element: _jsx(AgentPlaygroundPage, {}) }), _jsx(Route, { path: "/admin", element: _jsx(AdminPage, {}) }), _jsx(Route, { path: "/audit", element: _jsx(AuditPage, {}) })] }) }), _jsx(Route, { path: "*", element: _jsx(NotFoundPage, {}) })] }));
}
