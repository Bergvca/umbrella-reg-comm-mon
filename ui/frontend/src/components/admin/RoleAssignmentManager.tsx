import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { useState } from "react";
import { useAssignRoleToGroup, useRemoveRoleFromGroup } from "@/hooks/useGroups";
import { useRoles } from "@/hooks/useRoles";
import type { RoleOut } from "@/lib/types";

interface RoleAssignmentManagerProps {
  groupId: string;
  assignedRoles: RoleOut[];
}

export function RoleAssignmentManager({ groupId, assignedRoles }: RoleAssignmentManagerProps) {
  const { data: allRoles } = useRoles();
  const assignMutation = useAssignRoleToGroup(groupId);
  const removeMutation = useRemoveRoleFromGroup(groupId);
  const [selectedRole, setSelectedRole] = useState("");

  const assignedRoleIds = new Set(assignedRoles.map((r) => r.id));
  const availableRoles = allRoles?.filter((r) => !assignedRoleIds.has(r.id)) ?? [];

  return (
    <div className="space-y-2">
      <p className="text-sm font-medium">Roles</p>
      <div className="flex flex-wrap gap-2">
        {assignedRoles.map((r) => (
          <Badge key={r.id} variant="secondary" className="flex items-center gap-1">
            {r.name}
            <button
              className="ml-1 text-muted-foreground hover:text-foreground"
              onClick={() => removeMutation.mutate(r.id)}
            >
              ×
            </button>
          </Badge>
        ))}
        {!assignedRoles.length && <span className="text-xs text-muted-foreground">No roles assigned.</span>}
      </div>
      {availableRoles.length > 0 && (
        <div className="flex gap-2 items-center">
          <Select value={selectedRole} onValueChange={setSelectedRole}>
            <SelectTrigger className="w-40"><SelectValue placeholder="Add role…" /></SelectTrigger>
            <SelectContent>
              {availableRoles.map((r) => (
                <SelectItem key={r.id} value={String(r.id)}>{r.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button size="sm" disabled={!selectedRole || assignMutation.isPending}
            onClick={() => { assignMutation.mutate(selectedRole, { onSuccess: () => setSelectedRole("") }); }}>
            Add
          </Button>
        </div>
      )}
    </div>
  );
}
