import { jsxs as _jsxs, jsx as _jsx } from "react/jsx-runtime";
export function BatchProgress({ decided, total }) {
    const pct = total > 0 ? Math.round((decided / total) * 100) : 0;
    return (_jsxs("div", { className: "space-y-1", children: [_jsxs("div", { className: "flex justify-between text-xs text-muted-foreground", children: [_jsxs("span", { children: [decided, " of ", total, " reviewed"] }), _jsxs("span", { children: [pct, "%"] })] }), _jsx("div", { className: "h-1.5 w-full rounded-full bg-muted overflow-hidden", children: _jsx("div", { className: "h-full rounded-full bg-primary transition-all", style: { width: `${pct}%` } }) })] }));
}
