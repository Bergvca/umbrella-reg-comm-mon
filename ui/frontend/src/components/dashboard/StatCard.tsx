import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { LucideIcon } from "lucide-react";

interface StatCardProps {
  title: string;
  value: number;
  icon: LucideIcon;
  variant?: "default" | "critical" | "high" | "medium";
}

const VARIANT_STYLES: Record<string, string> = {
  default: "text-foreground",
  critical: "text-severity-critical",
  high: "text-severity-high",
  medium: "text-severity-medium",
};

export function StatCard({
  title,
  value,
  icon: Icon,
  variant = "default",
}: StatCardProps) {
  return (
    <Card>
      <CardContent className="flex items-center gap-4 p-4">
        <div
          className={cn(
            "flex h-10 w-10 items-center justify-center rounded-lg bg-muted",
            VARIANT_STYLES[variant],
          )}
        >
          <Icon className="h-5 w-5" />
        </div>
        <div>
          <p className="text-sm text-muted-foreground">{title}</p>
          <p className={cn("text-2xl font-bold", VARIANT_STYLES[variant])}>
            {value.toLocaleString()}
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
