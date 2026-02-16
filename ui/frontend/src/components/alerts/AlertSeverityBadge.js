import { jsx as _jsx } from "react/jsx-runtime";
import { Badge } from "@/components/ui/badge";
import { SEVERITY_COLORS } from "@/lib/constants";
export function AlertSeverityBadge({ severity }) {
    const colorClass = SEVERITY_COLORS[severity] ?? "";
    return (_jsx(Badge, { variant: "outline", className: colorClass, children: severity }));
}
