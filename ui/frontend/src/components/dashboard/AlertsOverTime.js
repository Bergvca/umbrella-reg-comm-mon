import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
export function AlertsOverTime({ data }) {
    const formatted = data.map((d) => ({
        ...d,
        date: new Date(d.date).toLocaleDateString(undefined, {
            month: "short",
            day: "numeric",
        }),
    }));
    return (_jsxs(Card, { children: [_jsx(CardHeader, { children: _jsx(CardTitle, { className: "text-base", children: "Alerts Over Time" }) }), _jsx(CardContent, { children: _jsx(ResponsiveContainer, { width: "100%", height: 280, children: _jsxs(AreaChart, { data: formatted, children: [_jsx(CartesianGrid, { strokeDasharray: "3 3", className: "stroke-border" }), _jsx(XAxis, { dataKey: "date", className: "text-xs" }), _jsx(YAxis, { className: "text-xs" }), _jsx(Tooltip, {}), _jsx(Area, { type: "monotone", dataKey: "count", stroke: "oklch(0.55 0.10 250)", fill: "oklch(0.55 0.10 250 / 0.2)" })] }) }) })] }));
}
