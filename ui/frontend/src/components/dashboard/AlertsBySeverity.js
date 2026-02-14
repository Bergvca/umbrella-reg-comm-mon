import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
const SEVERITY_BAR_COLORS = {
    critical: "oklch(0.55 0.22 25)",
    high: "oklch(0.65 0.20 40)",
    medium: "oklch(0.75 0.15 80)",
    low: "oklch(0.70 0.12 145)",
};
export function AlertsBySeverity({ data }) {
    // Sort critical → low
    const sorted = [...data].sort((a, b) => {
        const order = ["critical", "high", "medium", "low"];
        return order.indexOf(a.key) - order.indexOf(b.key);
    });
    return (_jsxs(Card, { children: [_jsx(CardHeader, { children: _jsx(CardTitle, { className: "text-base", children: "Alerts by Severity" }) }), _jsx(CardContent, { children: _jsx(ResponsiveContainer, { width: "100%", height: 280, children: _jsxs(BarChart, { data: sorted, children: [_jsx(CartesianGrid, { strokeDasharray: "3 3", className: "stroke-border" }), _jsx(XAxis, { dataKey: "key", className: "text-xs capitalize" }), _jsx(YAxis, { className: "text-xs" }), _jsx(Tooltip, {}), _jsx(Bar, { dataKey: "count", radius: [4, 4, 0, 0], children: sorted.map((entry) => (_jsx(Cell, { fill: SEVERITY_BAR_COLORS[entry.key] ?? "#888" }, entry.key))) })] }) }) })] }));
}
