import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { BucketCount } from "@/lib/types";

interface Props {
  data: BucketCount[];
}

const SEVERITY_BAR_COLORS: Record<string, string> = {
  critical: "oklch(0.55 0.22 25)",
  high: "oklch(0.65 0.20 40)",
  medium: "oklch(0.75 0.15 80)",
  low: "oklch(0.70 0.12 145)",
};

export function AlertsBySeverity({ data }: Props) {
  // Sort critical → low
  const sorted = [...data].sort((a, b) => {
    const order = ["critical", "high", "medium", "low"];
    return order.indexOf(a.key) - order.indexOf(b.key);
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Alerts by Severity</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={sorted}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
            <XAxis dataKey="key" className="text-xs capitalize" />
            <YAxis className="text-xs" />
            <Tooltip />
            <Bar dataKey="count" radius={[4, 4, 0, 0]}>
              {sorted.map((entry) => (
                <Cell
                  key={entry.key}
                  fill={SEVERITY_BAR_COLORS[entry.key] ?? "#888"}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
