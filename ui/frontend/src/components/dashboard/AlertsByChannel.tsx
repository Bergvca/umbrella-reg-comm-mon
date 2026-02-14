import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { BucketCount } from "@/lib/types";

interface Props {
  data: BucketCount[];
}

export function AlertsByChannel({ data }: Props) {
  const formatted = data.map((d) => ({
    ...d,
    label: d.key.replace(/_/g, " "),
  }));

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Alerts by Channel</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={formatted} layout="vertical">
            <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
            <XAxis type="number" className="text-xs" />
            <YAxis
              type="category"
              dataKey="label"
              width={120}
              className="text-xs capitalize"
            />
            <Tooltip />
            <Bar
              dataKey="count"
              fill="oklch(0.55 0.10 250)"
              radius={[0, 4, 4, 0]}
            />
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
