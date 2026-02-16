import { Badge } from "@/components/ui/badge";
import type { AlertStatus } from "@/lib/types";

const STATUS_CLASSES: Record<AlertStatus, string> = {
  open: "text-blue-600 bg-blue-50 border-blue-200",
  in_review: "text-yellow-600 bg-yellow-50 border-yellow-200",
  closed: "text-green-600 bg-green-50 border-green-200",
};

const STATUS_LABELS: Record<AlertStatus, string> = {
  open: "Open",
  in_review: "In Review",
  closed: "Closed",
};

interface Props {
  status: AlertStatus;
}

export function AlertStatusBadge({ status }: Props) {
  return (
    <Badge variant="outline" className={STATUS_CLASSES[status]}>
      {STATUS_LABELS[status]}
    </Badge>
  );
}
