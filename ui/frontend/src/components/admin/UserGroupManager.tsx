import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useState } from "react";
import { useUserGroups, useAddUserToGroup, useRemoveUserFromGroup } from "@/hooks/useUsers";
import { useGroups } from "@/hooks/useGroups";

interface UserGroupManagerProps {
  userId: string;
}

export function UserGroupManager({ userId }: UserGroupManagerProps) {
  const { data: userGroups } = useUserGroups(userId);
  const { data: allGroupsData } = useGroups();
  const addMutation = useAddUserToGroup(userId);
  const removeMutation = useRemoveUserFromGroup(userId);
  const [selectedGroup, setSelectedGroup] = useState("");

  const userGroupIds = new Set(userGroups?.map((g) => g.id));
  const availableGroups = allGroupsData?.items?.filter((g) => !userGroupIds.has(g.id)) ?? [];

  return (
    <div className="space-y-2">
      <p className="text-sm font-medium">Group Memberships</p>
      {userGroups?.map((g) => (
        <div key={g.id} className="flex items-center gap-2 border rounded p-2 text-sm">
          <span className="flex-1">{g.name}</span>
          <Button size="sm" variant="ghost" className="text-destructive hover:text-destructive"
            onClick={() => removeMutation.mutate(g.id)}>
            Remove
          </Button>
        </div>
      ))}
      {!userGroups?.length && <p className="text-xs text-muted-foreground">No group memberships.</p>}
      {availableGroups.length > 0 && (
        <div className="flex gap-2 items-center pt-1">
          <Select value={selectedGroup} onValueChange={setSelectedGroup}>
            <SelectTrigger className="w-48"><SelectValue placeholder="Add to group…" /></SelectTrigger>
            <SelectContent>
              {availableGroups.map((g) => (
                <SelectItem key={g.id} value={String(g.id)}>{g.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button size="sm" disabled={!selectedGroup || addMutation.isPending}
            onClick={() => { addMutation.mutate(selectedGroup, { onSuccess: () => setSelectedGroup("") }); }}>
            Add
          </Button>
        </div>
      )}
    </div>
  );
}
