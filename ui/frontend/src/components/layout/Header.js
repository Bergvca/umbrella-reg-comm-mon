import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useAuthStore } from "@/stores/auth";
import { useLogout } from "@/hooks/useAuth";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger, } from "@/components/ui/dropdown-menu";
import { LogOut, User as UserIcon } from "lucide-react";
export function Header() {
    const user = useAuthStore((s) => s.user);
    const logout = useLogout();
    const initials = user?.username
        ?.split(/[._-]/)
        .map((s) => s[0]?.toUpperCase())
        .join("")
        .slice(0, 2) ?? "?";
    const primaryRole = user?.roles?.[0] ?? "viewer";
    return (_jsxs("header", { className: "flex h-14 items-center justify-between border-b bg-card px-6", children: [_jsx("div", {}), " ", _jsxs(DropdownMenu, { children: [_jsxs(DropdownMenuTrigger, { className: "flex items-center gap-2 outline-none", children: [_jsx(Badge, { variant: "secondary", className: "text-xs capitalize", children: primaryRole }), _jsx(Avatar, { className: "h-8 w-8", children: _jsx(AvatarFallback, { className: "text-xs", children: initials }) })] }), _jsxs(DropdownMenuContent, { align: "end", className: "w-48", children: [_jsxs("div", { className: "px-2 py-1.5", children: [_jsx("p", { className: "text-sm font-medium", children: user?.username }), _jsx("p", { className: "text-xs text-muted-foreground", children: user?.email })] }), _jsx(DropdownMenuSeparator, {}), _jsxs(DropdownMenuItem, { children: [_jsx(UserIcon, { className: "mr-2 h-4 w-4" }), "Profile"] }), _jsx(DropdownMenuSeparator, {}), _jsxs(DropdownMenuItem, { onClick: logout, className: "text-destructive", children: [_jsx(LogOut, { className: "mr-2 h-4 w-4" }), "Logout"] })] })] })] }));
}
