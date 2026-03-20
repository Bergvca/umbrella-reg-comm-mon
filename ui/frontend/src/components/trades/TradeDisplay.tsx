import { Link } from "react-router";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { formatDateTime } from "@/lib/utils";
import type { TradeRecord } from "@/lib/types";

function formatCurrency(value: number | undefined, currency?: string): string {
  if (value == null) return "—";
  return `${currency === "USD" ? "$" : ""}${value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function formatQuantity(value: number | undefined): string {
  if (value == null) return "—";
  return value.toLocaleString();
}

interface TradeDisplayProps {
  trade: TradeRecord;
}

export function TradeDisplay({ trade }: TradeDisplayProps) {
  const m = trade.metadata;
  const isBuy = m.side?.toLowerCase() === "buy";
  const trader = trade.participants.find((p) => p.role === "trader");
  const counterparty = trade.participants.find((p) => p.role === "counterparty");

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <h2 className="text-xl font-semibold">{m.ticker ?? "Trade"}</h2>
        <Badge
          variant="outline"
          className={isBuy ? "text-green-600 border-green-300" : "text-red-600 border-red-300"}
        >
          {m.side?.toUpperCase() ?? "—"}
        </Badge>
        <span className="text-sm text-muted-foreground">
          {formatDateTime(trade.timestamp)}
        </span>
      </div>

      {trade.body_text && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Summary</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="font-mono">{trade.body_text}</p>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Trade Details</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
            <div>
              <dt className="text-muted-foreground">Ticker</dt>
              <dd className="font-mono font-medium">{m.ticker ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Side</dt>
              <dd>{m.side?.toUpperCase() ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Quantity</dt>
              <dd className="font-mono">{formatQuantity(m.quantity)}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Price</dt>
              <dd className="font-mono">{formatCurrency(m.price, m.currency)}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Notional</dt>
              <dd className="font-mono">{formatCurrency(m.notional, m.currency)}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Currency</dt>
              <dd>{m.currency ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Order Type</dt>
              <dd>{m.order_type ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Venue</dt>
              <dd>{m.venue ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Asset Class</dt>
              <dd>{m.asset_class ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Execution ID</dt>
              <dd className="font-mono text-xs">{m.execution_id ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Order ID</dt>
              <dd className="font-mono text-xs">{m.order_id ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Account</dt>
              <dd className="font-mono text-xs">{m.account_id ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Settlement Date</dt>
              <dd>{m.settlement_date ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Direction</dt>
              <dd>{trade.direction ?? "—"}</dd>
            </div>
          </dl>
        </CardContent>
      </Card>

      {(trader || counterparty) && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Participants</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {trader && (
                <div className="flex items-center gap-3">
                  <Badge variant="outline">Trader</Badge>
                  <span className="text-sm">{trader.name}</span>
                  {trader.entity_id && (
                    <Link
                      to={`/entities/${trader.entity_id}`}
                      className="text-xs text-primary hover:underline"
                    >
                      View entity
                    </Link>
                  )}
                </div>
              )}
              {counterparty && (
                <div className="flex items-center gap-3">
                  <Badge variant="outline">Counterparty</Badge>
                  <span className="text-sm">{counterparty.name}</span>
                  {counterparty.entity_id && (
                    <Link
                      to={`/entities/${counterparty.entity_id}`}
                      className="text-xs text-primary hover:underline"
                    >
                      View entity
                    </Link>
                  )}
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
