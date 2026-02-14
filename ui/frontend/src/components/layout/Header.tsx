import { useAuthStore } from "@/stores/auth";
import { useLogout } from "@/hooks/useAuth";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { LogOut, User as UserIcon } from "lucide-react";

export function Header() {
  const user = useAuthStore((s) => s.user);
  const logout = useLogout();

  const initials =
    user?.username
      ?.split(/[._-]/)
      .map((s) => s[0]?.toUpperCase())
      .join("")
      .slice(0, 2) ?? "?";

  const primaryRole = user?.roles?.[0] ?? "viewer";

  return (
    <header className="flex h-14 items-center justify-between border-b bg-card px-6">
      <div /> {/* Left side — breadcrumbs or search (Phase 5+) */}

      <DropdownMenu>
        <DropdownMenuTrigger className="flex items-center gap-2 outline-none">
          <Badge variant="secondary" className="text-xs capitalize">
            {primaryRole}
          </Badge>
          <Avatar className="h-8 w-8">
            <AvatarFallback className="text-xs">{initials}</AvatarFallback>
          </Avatar>
        </DropdownMenuTrigger>

        <DropdownMenuContent align="end" className="w-48">
          <div className="px-2 py-1.5">
            <p className="text-sm font-medium">{user?.username}</p>
            <p className="text-xs text-muted-foreground">{user?.email}</p>
          </div>
          <DropdownMenuSeparator />
          <DropdownMenuItem>
            <UserIcon className="mr-2 h-4 w-4" />
            Profile
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={logout} className="text-destructive">
            <LogOut className="mr-2 h-4 w-4" />
            Logout
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </header>
  );
}
