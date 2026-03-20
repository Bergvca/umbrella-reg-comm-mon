import { useSearchParams } from "react-router";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { TradeBlotter } from "@/components/trades/TradeBlotter";
import { useTradeSearch } from "@/hooks/useTrades";
import type { TradeSearchParams } from "@/api/trades";

const LIMIT = 20;

export function TradesPage() {
  const [searchParams, setSearchParams] = useSearchParams();

  const params: TradeSearchParams = {
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

  const hasSearched = !!(
    params.q ||
    params.ticker ||
    params.side ||
    params.participant ||
    params.date_from
  );

  function updateParams(updates: Partial<TradeSearchParams>) {
    const next = { ...params, ...updates, offset: 0 };
    const p: Record<string, string> = {};
    if (next.q) p.q = next.q;
    if (next.ticker) p.ticker = next.ticker;
    if (next.side) p.side = next.side;
    if (next.participant) p.participant = next.participant;
    if (next.venue) p.venue = next.venue;
    if (next.date_from) p.date_from = next.date_from;
    if (next.date_to) p.date_to = next.date_to;
    if (next.quantity_min != null) p.quantity_min = String(next.quantity_min);
    setSearchParams(p);
  }

  function handlePageChange(newOffset: number) {
    const p: Record<string, string> = {};
    if (params.q) p.q = params.q;
    if (params.ticker) p.ticker = params.ticker;
    if (params.side) p.side = params.side;
    if (params.participant) p.participant = params.participant;
    if (params.venue) p.venue = params.venue;
    if (params.date_from) p.date_from = params.date_from;
    if (params.date_to) p.date_to = params.date_to;
    if (params.quantity_min != null) p.quantity_min = String(params.quantity_min);
    if (newOffset > 0) p.offset = String(newOffset);
    setSearchParams(p);
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    // Trigger search by reading current form values from search params
    // The search is already reactive via useTradeSearch
  }

  return (
    <div className="space-y-6 max-w-5xl">
      <h1 className="text-2xl font-semibold">Trade Blotter</h1>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="space-y-1.5">
            <Label htmlFor="q">Search</Label>
            <Input
              id="q"
              placeholder="Free text..."
              value={params.q ?? ""}
              onChange={(e) => updateParams({ q: e.target.value || undefined })}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="ticker">Ticker</Label>
            <Input
              id="ticker"
              placeholder="e.g. MRDN"
              value={params.ticker ?? ""}
              onChange={(e) => updateParams({ ticker: e.target.value || undefined })}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="side">Side</Label>
            <Select
              value={params.side ?? "all"}
              onValueChange={(v) => updateParams({ side: v === "all" ? undefined : v })}
            >
              <SelectTrigger id="side">
                <SelectValue placeholder="All" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All</SelectItem>
                <SelectItem value="buy">Buy</SelectItem>
                <SelectItem value="sell">Sell</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="participant">Trader</Label>
            <Input
              id="participant"
              placeholder="Trader name..."
              value={params.participant ?? ""}
              onChange={(e) => updateParams({ participant: e.target.value || undefined })}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="date_from">From</Label>
            <Input
              id="date_from"
              type="date"
              value={params.date_from ?? ""}
              onChange={(e) => updateParams({ date_from: e.target.value || undefined })}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="date_to">To</Label>
            <Input
              id="date_to"
              type="date"
              value={params.date_to ?? ""}
              onChange={(e) => updateParams({ date_to: e.target.value || undefined })}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="venue">Venue</Label>
            <Input
              id="venue"
              placeholder="e.g. NYSE"
              value={params.venue ?? ""}
              onChange={(e) => updateParams({ venue: e.target.value || undefined })}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="quantity_min">Min Quantity</Label>
            <Input
              id="quantity_min"
              type="number"
              placeholder="e.g. 1000"
              value={params.quantity_min ?? ""}
              onChange={(e) => updateParams({ quantity_min: e.target.value ? Number(e.target.value) : undefined })}
            />
          </div>
        </div>

        <div className="flex gap-2">
          <Button type="submit" disabled={isLoading}>
            {isLoading ? "Searching..." : "Search"}
          </Button>
          <Button type="button" variant="outline" onClick={() => setSearchParams({})}>
            Clear
          </Button>
        </div>
      </form>

      {hasSearched && data && (
        <TradeBlotter
          hits={data.hits}
          total={data.total}
          offset={data.offset}
          limit={data.limit}
          onPageChange={handlePageChange}
        />
      )}

      {hasSearched && !data && !isLoading && (
        <div className="text-center py-12 text-muted-foreground">
          No trades match your search.
        </div>
      )}
    </div>
  );
}
