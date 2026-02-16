import { jsx as _jsx } from "react/jsx-runtime";
import { Badge } from "@/components/ui/badge";
const STATUS_CLASSES = {
    open: "text-blue-600 bg-blue-50 border-blue-200",
    in_review: "text-yellow-600 bg-yellow-50 border-yellow-200",
    closed: "text-green-600 bg-green-50 border-green-200",
};
const STATUS_LABELS = {
    open: "Open",
    in_review: "In Review",
    closed: "Closed",
};
export function AlertStatusBadge({ status }) {
    return (_jsx(Badge, { variant: "outline", className: STATUS_CLASSES[status], children: STATUS_LABELS[status] }));
}
