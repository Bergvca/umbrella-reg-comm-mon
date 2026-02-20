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
import { AdminPage } from "@/pages/AdminPage";
import { AuditPage } from "@/pages/AuditPage";
import { NotFoundPage } from "@/pages/NotFoundPage";

/** Redirects to /login if not authenticated */
function RequireAuth() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <Outlet />;
}

/** Redirects to / if already authenticated */
function GuestOnly() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  if (isAuthenticated) return <Navigate to="/" replace />;
  return <Outlet />;
}

export function App() {
  return (
    <Routes>
      {/* Public routes */}
      <Route element={<GuestOnly />}>
        <Route path="/login" element={<LoginPage />} />
      </Route>

      {/* Authenticated routes — wrapped in AppShell */}
      <Route element={<RequireAuth />}>
        <Route element={<AppShell />}>
          <Route index element={<DashboardPage />} />

          {/* Phase 5 routes */}
          <Route path="/alerts" element={<AlertsPage />} />
          <Route path="/alerts/:id" element={<AlertDetailPage />} />
          <Route path="/queues" element={<QueuesPage />} />
          <Route path="/queues/:id" element={<QueueDetailPage />} />
          <Route path="/queues/:queueId/batches/:batchId/review" element={<BatchReviewPage />} />

          {/* Phase 6 routes */}
          <Route path="/messages" element={<MessagesPage />} />
          <Route path="/messages/:index/:docId" element={<MessageDetailPage />} />
          <Route path="/policies" element={<PoliciesPage />} />

          {/* Entity resolution */}
          <Route path="/entities" element={<EntitiesPage />} />
          <Route path="/entities/:id" element={<EntityDetailPage />} />

          <Route path="/admin" element={<AdminPage />} />
          <Route path="/audit" element={<AuditPage />} />
        </Route>
      </Route>

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
