import { Badge } from "@/components/ui/badge";
import { SEVERITY_COLORS } from "@/lib/constants";
import type { Severity } from "@/lib/types";

interface Props {
  severity: Severity;
}

export function AlertSeverityBadge({ severity }: Props) {
  const colorClass = SEVERITY_COLORS[severity] ?? "";
  return (
    <Badge variant="outline" className={colorClass}>
      {severity}
    </Badge>
  );
}
