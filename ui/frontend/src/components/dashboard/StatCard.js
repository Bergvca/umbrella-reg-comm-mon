import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
const VARIANT_STYLES = {
    default: "text-foreground",
    critical: "text-severity-critical",
    high: "text-severity-high",
    medium: "text-severity-medium",
};
export function StatCard({ title, value, icon: Icon, variant = "default", }) {
    return (_jsx(Card, { children: _jsxs(CardContent, { className: "flex items-center gap-4 p-4", children: [_jsx("div", { className: cn("flex h-10 w-10 items-center justify-center rounded-lg bg-muted", VARIANT_STYLES[variant]), children: _jsx(Icon, { className: "h-5 w-5" }) }), _jsxs("div", { children: [_jsx("p", { className: "text-sm text-muted-foreground", children: title }), _jsx("p", { className: cn("text-2xl font-bold", VARIANT_STYLES[variant]), children: value.toLocaleString() })] })] }) }));
}
