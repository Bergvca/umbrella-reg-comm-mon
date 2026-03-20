import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Link } from "react-router";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { AlertMetadataCard } from "./AlertMetadataCard";
import { DecisionForm } from "./DecisionForm";
import { DecisionTimeline } from "./DecisionTimeline";
export function AlertSidePanel({ alert, decisions, loadingDecisions, onDecisionSuccess, positionLabel, }) {
    return (_jsxs("div", { className: "space-y-4", children: [positionLabel && (_jsx("p", { className: "text-sm text-muted-foreground text-center", children: positionLabel })), _jsx(AlertMetadataCard, { alert: alert }), alert.linked_entities?.length > 0 && (_jsxs("div", { children: [_jsx("h3", { className: "text-sm font-medium mb-2", children: "Linked Entities" }), _jsx("div", { className: "flex flex-wrap gap-1.5", children: alert.linked_entities.map((le) => (_jsx(Link, { to: `/entities/${le.entity_id}`, children: _jsx(Badge, { variant: "outline", className: "cursor-pointer hover:bg-accent", children: le.display_name }) }, le.entity_id))) })] })), _jsxs("div", { children: [_jsx("h3", { className: "text-sm font-medium mb-2", children: "Decision History" }), loadingDecisions ? (_jsx(Skeleton, { className: "h-24 w-full" })) : (_jsx(DecisionTimeline, { decisions: decisions }))] }), _jsx(DecisionForm, { alertId: alert.id, alertStatus: alert.status, onSuccess: onDecisionSuccess })] }));
}
