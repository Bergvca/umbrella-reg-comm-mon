import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState, useRef, useEffect } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
const ROLE_CLASSES = {
    from: "text-blue-600 border-blue-300",
    to: "text-gray-600 border-gray-300",
    cc: "text-muted-foreground border-muted",
};
function ParticipantChip({ participant: p }) {
    return (_jsxs("span", { className: "inline-flex items-center gap-1.5 text-sm whitespace-nowrap", children: [_jsx(Badge, { variant: "outline", className: `text-xs ${ROLE_CLASSES[p.role] ?? "text-muted-foreground"}`, children: p.role }), _jsx("span", { className: "font-medium", children: p.name }), p.id && p.id !== p.name && (_jsxs("span", { className: "text-muted-foreground", children: ["(", p.id, ")"] }))] }));
}
export function ParticipantList({ participants }) {
    const [expanded, setExpanded] = useState(false);
    const [visibleCount, setVisibleCount] = useState(participants.length);
    const containerRef = useRef(null);
    const measuringRef = useRef(null);
    useEffect(() => {
        if (expanded)
            return;
        function measure() {
            const container = containerRef.current;
            const measuring = measuringRef.current;
            if (!container || !measuring)
                return;
            const containerWidth = container.offsetWidth;
            const children = measuring.children;
            // Reserve space for the "+N" button (~48px)
            const buttonReserve = 48;
            let count = 0;
            let usedWidth = 0;
            for (let i = 0; i < children.length; i++) {
                const child = children[i];
                const childWidth = child.offsetWidth + 8; // 8px gap
                if (usedWidth + childWidth > containerWidth - buttonReserve && i > 0) {
                    break;
                }
                usedWidth += childWidth;
                count++;
            }
            setVisibleCount(count || 1);
        }
        measure();
        const observer = new ResizeObserver(measure);
        if (containerRef.current)
            observer.observe(containerRef.current);
        return () => observer.disconnect();
    }, [participants, expanded]);
    if (participants.length === 0) {
        return _jsx("p", { className: "text-sm text-muted-foreground", children: "No participants." });
    }
    const hiddenCount = expanded ? 0 : participants.length - visibleCount;
    const displayedParticipants = expanded
        ? participants
        : participants.slice(0, visibleCount);
    return (_jsxs("div", { ref: containerRef, className: "relative", children: [_jsx("div", { ref: measuringRef, className: "flex flex-wrap items-center gap-2 absolute invisible h-0 overflow-hidden", "aria-hidden": true, children: participants.map((p, i) => (_jsx(ParticipantChip, { participant: p }, i))) }), _jsxs("div", { className: `flex items-center gap-2 ${expanded ? "flex-wrap" : "flex-nowrap overflow-hidden"}`, children: [displayedParticipants.map((p, i) => (_jsx(ParticipantChip, { participant: p }, i))), hiddenCount > 0 && (_jsxs(Button, { variant: "outline", size: "sm", className: "h-6 px-2 text-xs shrink-0", onClick: () => setExpanded(true), children: ["+", hiddenCount] })), expanded && participants.length > 3 && (_jsx(Button, { variant: "ghost", size: "sm", className: "h-6 px-2 text-xs shrink-0", onClick: () => setExpanded(false), children: "Show less" }))] })] }));
}
