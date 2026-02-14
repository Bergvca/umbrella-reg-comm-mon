import { NavLink } from "react-router";
import {
  LayoutDashboard,
  AlertTriangle,
  Search,
  ListTodo,
  Shield,
  Users,
  FileText,
} from "lucide-react";
import { cn, hasRole } from "@/lib/utils";
import { useAuthStore } from "@/stores/auth";
import { Separator } from "@/components/ui/separator";

interface NavItem {
  to: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  minRole: string;
}

const NAV_ITEMS: NavItem[] = [
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

  const visibleItems = NAV_ITEMS.filter((item) =>
    hasRole(roles, item.minRole),
  );

  return (
    <aside className="flex w-64 flex-col border-r bg-card">
      {/* Brand */}
      <div className="flex h-14 items-center gap-2 px-4 font-semibold">
        <Shield className="h-6 w-6 text-brand-600" />
        <span className="text-lg">Umbrella</span>
      </div>

      <Separator />

      {/* Navigation */}
      <nav className="flex-1 space-y-1 p-2">
        {visibleItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
              )
            }
          >
            <item.icon className="h-4 w-4" />
            {item.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
