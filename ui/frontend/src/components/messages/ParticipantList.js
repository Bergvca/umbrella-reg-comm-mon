import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Badge } from "@/components/ui/badge";
const ROLE_CLASSES = {
    from: "text-blue-600 border-blue-300",
    to: "text-gray-600 border-gray-300",
    cc: "text-muted-foreground border-muted",
};
export function ParticipantList({ participants }) {
    if (participants.length === 0) {
        return _jsx("p", { className: "text-sm text-muted-foreground", children: "No participants." });
    }
    return (_jsx("ul", { className: "space-y-1", children: participants.map((p, i) => (_jsxs("li", { className: "flex items-center gap-2 text-sm", children: [_jsx(Badge, { variant: "outline", className: `text-xs ${ROLE_CLASSES[p.role] ?? "text-muted-foreground"}`, children: p.role }), _jsx("span", { className: "font-medium", children: p.name }), p.id && p.id !== p.name && (_jsxs("span", { className: "text-muted-foreground", children: ["(", p.id, ")"] }))] }, i))) }));
}
