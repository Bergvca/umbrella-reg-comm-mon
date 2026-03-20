import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useSearchParams } from "react-router";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue, } from "@/components/ui/select";
import { TradeBlotter } from "@/components/trades/TradeBlotter";
import { useTradeSearch } from "@/hooks/useTrades";
const LIMIT = 20;
export function TradesPage() {
    const [searchParams, setSearchParams] = useSearchParams();
    const params = {
        q: searchParams.get("q") ?? undefined,
        ticker: searchParams.get("ticker") ?? undefined,
        side: searchParams.get("side") ?? undefined,
        participant: searchParams.get("participant") ?? undefined,
        venue: searchParams.get("venue") ?? undefined,
        date_from: searchParams.get("date_from") ?? undefined,
        date_to: searchParams.get("date_to") ?? undefined,
        quantity_min: searchParams.get("quantity_min") ? Number(searchParams.get("quantity_min")) : undefined,
        offset: Number(searchParams.get("offset") ?? 0),
        limit: LIMIT,
    };
    const { data, isLoading } = useTradeSearch(params);
    const hasSearched = !!(params.q ||
        params.ticker ||
        params.side ||
        params.participant ||
        params.date_from);
    function updateParams(updates) {
        const next = { ...params, ...updates, offset: 0 };
        const p = {};
        if (next.q)
            p.q = next.q;
        if (next.ticker)
            p.ticker = next.ticker;
        if (next.side)
            p.side = next.side;
        if (next.participant)
            p.participant = next.participant;
        if (next.venue)
            p.venue = next.venue;
        if (next.date_from)
            p.date_from = next.date_from;
        if (next.date_to)
            p.date_to = next.date_to;
        if (next.quantity_min != null)
            p.quantity_min = String(next.quantity_min);
        setSearchParams(p);
    }
    function handlePageChange(newOffset) {
        const p = {};
        if (params.q)
            p.q = params.q;
        if (params.ticker)
            p.ticker = params.ticker;
        if (params.side)
            p.side = params.side;
        if (params.participant)
            p.participant = params.participant;
        if (params.venue)
            p.venue = params.venue;
        if (params.date_from)
            p.date_from = params.date_from;
        if (params.date_to)
            p.date_to = params.date_to;
        if (params.quantity_min != null)
            p.quantity_min = String(params.quantity_min);
        if (newOffset > 0)
            p.offset = String(newOffset);
        setSearchParams(p);
    }
    function handleSubmit(e) {
        e.preventDefault();
        // Trigger search by reading current form values from search params
        // The search is already reactive via useTradeSearch
    }
    return (_jsxs("div", { className: "space-y-6 max-w-5xl", children: [_jsx("h1", { className: "text-2xl font-semibold", children: "Trade Blotter" }), _jsxs("form", { onSubmit: handleSubmit, className: "space-y-4", children: [_jsxs("div", { className: "grid grid-cols-2 md:grid-cols-4 gap-4", children: [_jsxs("div", { className: "space-y-1.5", children: [_jsx(Label, { htmlFor: "q", children: "Search" }), _jsx(Input, { id: "q", placeholder: "Free text...", value: params.q ?? "", onChange: (e) => updateParams({ q: e.target.value || undefined }) })] }), _jsxs("div", { className: "space-y-1.5", children: [_jsx(Label, { htmlFor: "ticker", children: "Ticker" }), _jsx(Input, { id: "ticker", placeholder: "e.g. MRDN", value: params.ticker ?? "", onChange: (e) => updateParams({ ticker: e.target.value || undefined }) })] }), _jsxs("div", { className: "space-y-1.5", children: [_jsx(Label, { htmlFor: "side", children: "Side" }), _jsxs(Select, { value: params.side ?? "all", onValueChange: (v) => updateParams({ side: v === "all" ? undefined : v }), children: [_jsx(SelectTrigger, { id: "side", children: _jsx(SelectValue, { placeholder: "All" }) }), _jsxs(SelectContent, { children: [_jsx(SelectItem, { value: "all", children: "All" }), _jsx(SelectItem, { value: "buy", children: "Buy" }), _jsx(SelectItem, { value: "sell", children: "Sell" })] })] })] }), _jsxs("div", { className: "space-y-1.5", children: [_jsx(Label, { htmlFor: "participant", children: "Trader" }), _jsx(Input, { id: "participant", placeholder: "Trader name...", value: params.participant ?? "", onChange: (e) => updateParams({ participant: e.target.value || undefined }) })] }), _jsxs("div", { className: "space-y-1.5", children: [_jsx(Label, { htmlFor: "date_from", children: "From" }), _jsx(Input, { id: "date_from", type: "date", value: params.date_from ?? "", onChange: (e) => updateParams({ date_from: e.target.value || undefined }) })] }), _jsxs("div", { className: "space-y-1.5", children: [_jsx(Label, { htmlFor: "date_to", children: "To" }), _jsx(Input, { id: "date_to", type: "date", value: params.date_to ?? "", onChange: (e) => updateParams({ date_to: e.target.value || undefined }) })] }), _jsxs("div", { className: "space-y-1.5", children: [_jsx(Label, { htmlFor: "venue", children: "Venue" }), _jsx(Input, { id: "venue", placeholder: "e.g. NYSE", value: params.venue ?? "", onChange: (e) => updateParams({ venue: e.target.value || undefined }) })] }), _jsxs("div", { className: "space-y-1.5", children: [_jsx(Label, { htmlFor: "quantity_min", children: "Min Quantity" }), _jsx(Input, { id: "quantity_min", type: "number", placeholder: "e.g. 1000", value: params.quantity_min ?? "", onChange: (e) => updateParams({ quantity_min: e.target.value ? Number(e.target.value) : undefined }) })] })] }), _jsxs("div", { className: "flex gap-2", children: [_jsx(Button, { type: "submit", disabled: isLoading, children: isLoading ? "Searching..." : "Search" }), _jsx(Button, { type: "button", variant: "outline", onClick: () => setSearchParams({}), children: "Clear" })] })] }), hasSearched && data && (_jsx(TradeBlotter, { hits: data.hits, total: data.total, offset: data.offset, limit: data.limit, onPageChange: handlePageChange })), hasSearched && !data && !isLoading && (_jsx("div", { className: "text-center py-12 text-muted-foreground", children: "No trades match your search." }))] }));
}
