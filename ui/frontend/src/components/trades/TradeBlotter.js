import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useNavigate } from "react-router";
import { Badge } from "@/components/ui/badge";
import { Pagination, PaginationContent, PaginationItem, PaginationNext, PaginationPrevious, } from "@/components/ui/pagination";
import { formatDateTime } from "@/lib/utils";
function formatCurrency(value, currency) {
    if (value == null)
        return "—";
    return `${currency === "USD" ? "$" : ""}${value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}
function formatQuantity(value) {
    if (value == null)
        return "—";
    return value.toLocaleString();
}
export function TradeBlotter({ hits, total, offset, limit, onPageChange }) {
    const navigate = useNavigate();
    if (!hits.length) {
        return (_jsx("div", { className: "text-center py-12 text-muted-foreground", children: "No trades match your search." }));
    }
    const from = offset + 1;
    const to = offset + hits.length;
    return (_jsxs("div", { className: "space-y-4", children: [_jsxs("p", { className: "text-sm text-muted-foreground", children: ["Showing ", from, "\u2013", to, " of ", total, " trades"] }), _jsx("div", { className: "overflow-x-auto", children: _jsxs("table", { className: "w-full text-sm", children: [_jsx("thead", { children: _jsxs("tr", { className: "border-b text-left text-muted-foreground", children: [_jsx("th", { className: "pb-2 pr-4 font-medium", children: "Time" }), _jsx("th", { className: "pb-2 pr-4 font-medium", children: "Side" }), _jsx("th", { className: "pb-2 pr-4 font-medium", children: "Ticker" }), _jsx("th", { className: "pb-2 pr-4 font-medium text-right", children: "Qty" }), _jsx("th", { className: "pb-2 pr-4 font-medium text-right", children: "Price" }), _jsx("th", { className: "pb-2 pr-4 font-medium text-right", children: "Notional" }), _jsx("th", { className: "pb-2 pr-4 font-medium", children: "Venue" }), _jsx("th", { className: "pb-2 pr-4 font-medium", children: "Trader" })] }) }), _jsx("tbody", { children: hits.map((hit) => {
                                const m = hit.trade.metadata;
                                const trader = hit.trade.participants.find((p) => p.role === "trader");
                                const isBuy = m.side?.toLowerCase() === "buy";
                                return (_jsxs("tr", { className: "border-b cursor-pointer hover:bg-muted/50 transition-colors", onClick: () => void navigate(`/trades/${hit.index}/${hit.trade.message_id}`), children: [_jsx("td", { className: "py-2 pr-4 whitespace-nowrap", children: formatDateTime(hit.trade.timestamp) }), _jsx("td", { className: "py-2 pr-4", children: _jsx(Badge, { variant: "outline", className: isBuy ? "text-green-600 border-green-300" : "text-red-600 border-red-300", children: m.side?.toUpperCase() ?? "—" }) }), _jsx("td", { className: "py-2 pr-4 font-mono font-medium", children: m.ticker ?? "—" }), _jsx("td", { className: "py-2 pr-4 text-right font-mono", children: formatQuantity(m.quantity) }), _jsx("td", { className: "py-2 pr-4 text-right font-mono", children: formatCurrency(m.price, m.currency) }), _jsx("td", { className: "py-2 pr-4 text-right font-mono", children: formatCurrency(m.notional, m.currency) }), _jsx("td", { className: "py-2 pr-4", children: m.venue ?? "—" }), _jsx("td", { className: "py-2 pr-4", children: trader?.name ?? "—" })] }, `${hit.index}/${hit.trade.message_id}`));
                            }) })] }) }), total > limit && (_jsx(Pagination, { children: _jsxs(PaginationContent, { children: [_jsx(PaginationItem, { children: _jsx(PaginationPrevious, { onClick: () => onPageChange(Math.max(0, offset - limit)), "aria-disabled": offset === 0, className: offset === 0 ? "pointer-events-none opacity-50" : "cursor-pointer" }) }), _jsx(PaginationItem, { children: _jsx(PaginationNext, { onClick: () => onPageChange(offset + limit), "aria-disabled": offset + limit >= total, className: offset + limit >= total ? "pointer-events-none opacity-50" : "cursor-pointer" }) })] }) }))] }));
}
