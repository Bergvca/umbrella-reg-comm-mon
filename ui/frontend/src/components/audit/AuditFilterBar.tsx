import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import type { AuditLogParams } from "@/api/audit";

interface AuditFilterBarProps {
  params: AuditLogParams;
  onChange: (params: AuditLogParams) => void;
}

export function AuditFilterBar({ params, onChange }: AuditFilterBarProps) {
  return (
    <div className="border rounded-lg p-4 space-y-4 bg-muted/30">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="space-y-1">
          <Label>Actor</Label>
          <Input
            placeholder="User ID or email"
            value={params.actor_id ?? ""}
            onChange={(e) => onChange({ ...params, actor_id: e.target.value || undefined })}
          />
        </div>
        <div className="space-y-1">
          <Label>Object Type</Label>
          <Select value={params.object_type ?? "all"} onValueChange={(v) => onChange({ ...params, object_type: v === "all" ? undefined : v })}>
            <SelectTrigger><SelectValue placeholder="All" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All</SelectItem>
              <SelectItem value="user">User</SelectItem>
              <SelectItem value="group">Group</SelectItem>
              <SelectItem value="policy">Policy</SelectItem>
              <SelectItem value="rule">Rule</SelectItem>
              <SelectItem value="queue">Queue</SelectItem>
              <SelectItem value="alert">Alert</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1">
          <Label>Date From</Label>
          <Input
            type="date"
            value={params.date_from ?? ""}
            onChange={(e) => onChange({ ...params, date_from: e.target.value || undefined })}
          />
        </div>
        <div className="space-y-1">
          <Label>Date To</Label>
          <Input
            type="date"
            value={params.date_to ?? ""}
            onChange={(e) => onChange({ ...params, date_to: e.target.value || undefined })}
          />
        </div>
      </div>
      <Button variant="ghost" size="sm" onClick={() => onChange({})}>Clear filters</Button>
    </div>
  );
}
