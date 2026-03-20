import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useNavigate } from "react-router";
import { Badge } from "@/components/ui/badge";
import { Pagination, PaginationContent, PaginationItem, PaginationNext, PaginationPrevious } from "@/components/ui/pagination";
import { MessageHighlight } from "./MessageHighlight";
import { formatDateTime } from "@/lib/utils";
export function MessageSearchResults({ results, total, offset, limit, onPageChange, }) {
    const navigate = useNavigate();
    if (!results.length) {
        return (_jsx("div", { className: "text-center py-12 text-muted-foreground", children: "No messages match your search." }));
    }
    const from = offset + 1;
    const to = offset + results.length;
    return (_jsxs("div", { className: "space-y-4", children: [_jsxs("p", { className: "text-sm text-muted-foreground", children: ["Showing ", from, "\u2013", to, " of ", total, " results"] }), _jsx("div", { className: "space-y-2", children: results.map((hit) => {
                    const highlights = Object.values(hit.highlights).flat();
                    const sender = hit.message.participants.find((p) => p.role === "sender");
                    const receiver = hit.message.participants.find((p) => p.role === "receiver" || p.role === "recipient");
                    return (_jsxs("div", { className: "border rounded-lg p-4 cursor-pointer hover:bg-muted/50 transition-colors space-y-2", onClick: () => void navigate(`/messages/${hit.index}/${hit.message.message_id}`), children: [_jsxs("div", { className: "flex items-center justify-between", children: [_jsxs("div", { className: "flex items-center gap-2", children: [_jsx(Badge, { variant: "outline", children: hit.message.channel }), _jsx("span", { className: "text-sm text-muted-foreground", children: formatDateTime(hit.message.timestamp) })] }), hit.score != null && (_jsxs("span", { className: "text-xs text-muted-foreground", children: ["Score: ", hit.score.toFixed(1)] }))] }), (sender || receiver) && (_jsxs("p", { className: "text-sm", children: [sender?.name ?? "Unknown", receiver && _jsxs(_Fragment, { children: [" \u2192 ", receiver.name] })] })), highlights.length > 0 && (_jsx(MessageHighlight, { fragments: highlights.slice(0, 2) }))] }, `${hit.index}/${hit.message.message_id}`));
                }) }), total > limit && (_jsx(Pagination, { children: _jsxs(PaginationContent, { children: [_jsx(PaginationItem, { children: _jsx(PaginationPrevious, { onClick: () => onPageChange(Math.max(0, offset - limit)), "aria-disabled": offset === 0, className: offset === 0 ? "pointer-events-none opacity-50" : "cursor-pointer" }) }), _jsx(PaginationItem, { children: _jsx(PaginationNext, { onClick: () => onPageChange(offset + limit), "aria-disabled": offset + limit >= total, className: offset + limit >= total ? "pointer-events-none opacity-50" : "cursor-pointer" }) })] }) }))] }));
}
