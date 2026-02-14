import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Link } from "react-router";
import { Button } from "@/components/ui/button";
export function NotFoundPage() {
    return (_jsxs("div", { className: "flex min-h-screen flex-col items-center justify-center gap-4", children: [_jsx("h1", { className: "text-6xl font-bold text-muted-foreground", children: "404" }), _jsx("p", { className: "text-muted-foreground", children: "Page not found" }), _jsx(Button, { asChild: true, variant: "outline", children: _jsx(Link, { to: "/", children: "Back to Dashboard" }) })] }));
}
