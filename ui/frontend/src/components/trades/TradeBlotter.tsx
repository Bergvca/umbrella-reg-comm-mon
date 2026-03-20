import { useNavigate } from "react-router";
import { Badge } from "@/components/ui/badge";
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination";
import { formatDateTime } from "@/lib/utils";
import type { TradeHit } from "@/api/trades";

function formatCurrency(value: number | undefined, currency?: string): string {
  if (value == null) return "—";
  return `${currency === "USD" ? "$" : ""}${value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function formatQuantity(value: number | undefined): string {
  if (value == null) return "—";
  return value.toLocaleString();
}

interface TradeBlotterProps {
  hits: TradeHit[];
  total: number;
  offset: number;
  limit: number;
  onPageChange: (offset: number) => void;
}

export function TradeBlotter({ hits, total, offset, limit, onPageChange }: TradeBlotterProps) {
  const navigate = useNavigate();

  if (!hits.length) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        No trades match your search.
      </div>
    );
  }

  const from = offset + 1;
  const to = offset + hits.length;

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        Showing {from}–{to} of {total} trades
      </p>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left text-muted-foreground">
              <th className="pb-2 pr-4 font-medium">Time</th>
              <th className="pb-2 pr-4 font-medium">Side</th>
              <th className="pb-2 pr-4 font-medium">Ticker</th>
              <th className="pb-2 pr-4 font-medium text-right">Qty</th>
              <th className="pb-2 pr-4 font-medium text-right">Price</th>
              <th className="pb-2 pr-4 font-medium text-right">Notional</th>
              <th className="pb-2 pr-4 font-medium">Venue</th>
              <th className="pb-2 pr-4 font-medium">Trader</th>
            </tr>
          </thead>
          <tbody>
            {hits.map((hit) => {
              const m = hit.trade.metadata;
              const trader = hit.trade.participants.find((p) => p.role === "trader");
              const isBuy = m.side?.toLowerCase() === "buy";

              return (
                <tr
                  key={`${hit.index}/${hit.trade.message_id}`}
                  className="border-b cursor-pointer hover:bg-muted/50 transition-colors"
                  onClick={() => void navigate(`/trades/${hit.index}/${hit.trade.message_id}`)}
                >
                  <td className="py-2 pr-4 whitespace-nowrap">
                    {formatDateTime(hit.trade.timestamp)}
                  </td>
                  <td className="py-2 pr-4">
                    <Badge
                      variant="outline"
                      className={isBuy ? "text-green-600 border-green-300" : "text-red-600 border-red-300"}
                    >
                      {m.side?.toUpperCase() ?? "—"}
                    </Badge>
                  </td>
                  <td className="py-2 pr-4 font-mono font-medium">
                    {m.ticker ?? "—"}
                  </td>
                  <td className="py-2 pr-4 text-right font-mono">
                    {formatQuantity(m.quantity)}
                  </td>
                  <td className="py-2 pr-4 text-right font-mono">
                    {formatCurrency(m.price, m.currency)}
                  </td>
                  <td className="py-2 pr-4 text-right font-mono">
                    {formatCurrency(m.notional, m.currency)}
                  </td>
                  <td className="py-2 pr-4">{m.venue ?? "—"}</td>
                  <td className="py-2 pr-4">{trader?.name ?? "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {total > limit && (
        <Pagination>
          <PaginationContent>
            <PaginationItem>
              <PaginationPrevious
                onClick={() => onPageChange(Math.max(0, offset - limit))}
                aria-disabled={offset === 0}
                className={offset === 0 ? "pointer-events-none opacity-50" : "cursor-pointer"}
              />
            </PaginationItem>
            <PaginationItem>
              <PaginationNext
                onClick={() => onPageChange(offset + limit)}
                aria-disabled={offset + limit >= total}
                className={offset + limit >= total ? "pointer-events-none opacity-50" : "cursor-pointer"}
              />
            </PaginationItem>
          </PaginationContent>
        </Pagination>
      )}
    </div>
  );
}
