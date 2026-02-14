import { Routes, Route, Navigate, Outlet } from "react-router";
import { useAuthStore } from "@/stores/auth";
import { AppShell } from "@/components/layout/AppShell";
import { LoginPage } from "@/pages/LoginPage";
import { DashboardPage } from "@/pages/DashboardPage";
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

/** Temporary placeholder for routes not yet implemented */
function ComingSoon({ label }: { label: string }) {
  return (
    <div className="flex items-center justify-center h-full">
      <p className="text-muted-foreground text-lg">{label} — coming in Phase 5</p>
    </div>
  );
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

          {/* Placeholder routes for Phase 5+ pages */}
          <Route path="/alerts" element={<ComingSoon label="Alerts" />} />
          <Route path="/alerts/:id" element={<ComingSoon label="Alert Detail" />} />
          <Route path="/messages" element={<ComingSoon label="Messages" />} />
          <Route path="/queues" element={<ComingSoon label="Queues" />} />
          <Route path="/policies" element={<ComingSoon label="Policies" />} />
          <Route path="/admin" element={<ComingSoon label="Admin" />} />
          <Route path="/audit" element={<ComingSoon label="Audit Log" />} />
        </Route>
      </Route>

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
