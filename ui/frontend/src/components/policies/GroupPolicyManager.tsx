import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useState } from "react";
import { useGroupPolicies, useAssignGroupPolicy, useRemoveGroupPolicy } from "@/hooks/usePolicies";
import { useGroups } from "@/hooks/useGroups";

interface GroupPolicyManagerProps {
  policyId: string;
  canEdit: boolean;
}

export function GroupPolicyManager({ policyId, canEdit }: GroupPolicyManagerProps) {
  const { data: assignments } = useGroupPolicies(policyId);
  const { data: groupsData } = useGroups();
  const assignMutation = useAssignGroupPolicy(policyId);
  const removeMutation = useRemoveGroupPolicy(policyId);
  const [selectedGroup, setSelectedGroup] = useState("");

  const assignedGroupIds = new Set(assignments?.map((a) => a.group_id));
  const availableGroups = groupsData?.items?.filter((g) => !assignedGroupIds.has(g.id)) ?? [];

  return (
    <div className="space-y-2">
      {assignments?.map((a) => (
        <div key={a.group_id} className="flex items-center gap-3 border rounded p-2 text-sm">
          <span className="flex-1">{a.group_name ?? a.group_id}</span>
          {canEdit && (
            <Button size="sm" variant="ghost" className="text-destructive hover:text-destructive"
              onClick={() => removeMutation.mutate(a.group_id)}>
              Remove
            </Button>
          )}
        </div>
      ))}
      {!assignments?.length && <p className="text-sm text-muted-foreground">No groups assigned.</p>}
      {canEdit && availableGroups.length > 0 && (
        <div className="flex gap-2 items-center pt-1">
          <Select value={selectedGroup} onValueChange={setSelectedGroup}>
            <SelectTrigger className="w-48"><SelectValue placeholder="Add group…" /></SelectTrigger>
            <SelectContent>
              {availableGroups.map((g) => (
                <SelectItem key={g.id} value={String(g.id)}>{g.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button size="sm" disabled={!selectedGroup || assignMutation.isPending}
            onClick={() => { assignMutation.mutate(selectedGroup, { onSuccess: () => setSelectedGroup("") }); }}>
            Assign
          </Button>
        </div>
      )}
    </div>
  );
}
