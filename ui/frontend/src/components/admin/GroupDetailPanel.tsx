import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { useGroupMembers } from "@/hooks/useGroups";
import { RoleAssignmentManager } from "./RoleAssignmentManager";
import type { GroupDetail } from "@/lib/types";

interface GroupDetailPanelProps {
  group: GroupDetail;
}

export function GroupDetailPanel({ group }: GroupDetailPanelProps) {
  const { data: members, isLoading } = useGroupMembers(group.id);

  return (
    <div className="space-y-4">
      {group.description && <p className="text-sm text-muted-foreground">{group.description}</p>}
      <Separator />
      <RoleAssignmentManager groupId={group.id} assignedRoles={group.roles ?? []} />
      <Separator />
      <div className="space-y-2">
        <p className="text-sm font-medium">Members</p>
        {isLoading && <Skeleton className="h-16 w-full" />}
        {members?.map((m) => (
          <div key={m.id} className="text-sm border rounded p-2">
            {m.full_name ?? m.email}
          </div>
        ))}
        {!isLoading && !members?.length && (
          <p className="text-xs text-muted-foreground">No members.</p>
        )}
      </div>
    </div>
  );
}
