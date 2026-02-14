import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
export function AlertsByChannel({ data }) {
    const formatted = data.map((d) => ({
        ...d,
        label: d.key.replace(/_/g, " "),
    }));
    return (_jsxs(Card, { children: [_jsx(CardHeader, { children: _jsx(CardTitle, { className: "text-base", children: "Alerts by Channel" }) }), _jsx(CardContent, { children: _jsx(ResponsiveContainer, { width: "100%", height: 280, children: _jsxs(BarChart, { data: formatted, layout: "vertical", children: [_jsx(CartesianGrid, { strokeDasharray: "3 3", className: "stroke-border" }), _jsx(XAxis, { type: "number", className: "text-xs" }), _jsx(YAxis, { type: "category", dataKey: "label", width: 120, className: "text-xs capitalize" }), _jsx(Tooltip, {}), _jsx(Bar, { dataKey: "count", fill: "oklch(0.55 0.10 250)", radius: [0, 4, 4, 0] })] }) }) })] }));
}
