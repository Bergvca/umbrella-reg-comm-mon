import { useSearchParams } from "react-router";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { SEVERITY_LEVELS, ALERT_STATUSES } from "@/lib/constants";

interface Filters {
  severity?: string;
  status?: string;
}

interface Props {
  filters: Filters;
  onChange: (filters: Filters) => void;
}

export function AlertFilters({ filters, onChange }: Props) {
  const [, setSearchParams] = useSearchParams();

  function update(patch: Partial<Filters>) {
    const next = { ...filters, ...patch };
    // remove undefined/empty values
    const params: Record<string, string> = {};
    if (next.severity) params.severity = next.severity;
    if (next.status) params.status = next.status;
    setSearchParams(params);
    onChange(next);
  }

  function clear() {
    setSearchParams({});
    onChange({});
  }

  return (
    <div className="flex flex-wrap items-center gap-3">
      <div className="flex items-center gap-2">
        <span className="text-sm font-medium text-muted-foreground">Severity:</span>
        <Select
          value={filters.severity ?? "all"}
          onValueChange={(v) => update({ severity: v === "all" ? undefined : v })}
        >
          <SelectTrigger className="w-32">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All</SelectItem>
            {SEVERITY_LEVELS.map((s) => (
              <SelectItem key={s} value={s}>
                {s.charAt(0).toUpperCase() + s.slice(1)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="flex items-center gap-2">
        <span className="text-sm font-medium text-muted-foreground">Status:</span>
        <Select
          value={filters.status ?? "all"}
          onValueChange={(v) => update({ status: v === "all" ? undefined : v })}
        >
          <SelectTrigger className="w-36">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All</SelectItem>
            {ALERT_STATUSES.map((s) => (
              <SelectItem key={s} value={s}>
                {s === "in_review" ? "In Review" : s.charAt(0).toUpperCase() + s.slice(1)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {(filters.severity ?? filters.status) && (
        <Button variant="ghost" size="sm" onClick={clear}>
          Clear filters
        </Button>
      )}
    </div>
  );
}
