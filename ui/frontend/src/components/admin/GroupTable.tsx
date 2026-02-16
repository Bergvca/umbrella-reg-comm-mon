import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { useGroups } from "@/hooks/useGroups";
import { GroupForm } from "./GroupForm";
import { GroupDetailPanel } from "./GroupDetailPanel";
import type { GroupDetail } from "@/lib/types";

export function GroupTable() {
  const { data: groups, isLoading } = useGroups();
  const [showAdd, setShowAdd] = useState(false);
  const [editGroup, setEditGroup] = useState<GroupDetail | null>(null);
  const [detailGroup, setDetailGroup] = useState<GroupDetail | null>(null);

  if (isLoading) return <Skeleton className="h-48 w-full" />;

  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <Button onClick={() => setShowAdd(true)}>+ Add Group</Button>
      </div>
      <div className="border rounded-lg divide-y">
        {!groups?.items?.length && <p className="p-4 text-sm text-muted-foreground">No groups found.</p>}
        {groups?.items?.map((g) => (
          <div key={g.id} className="flex items-center gap-3 p-3">
            <div className="flex-1">
              <p className="text-sm font-medium">{g.name}</p>
              {g.description && <p className="text-xs text-muted-foreground">{g.description}</p>}
            </div>
            <Button size="sm" variant="ghost" onClick={() => setDetailGroup(g as GroupDetail)}>Manage</Button>
            <Button size="sm" variant="outline" onClick={() => setEditGroup(g as GroupDetail)}>Edit</Button>
          </div>
        ))}
      </div>
      <Dialog open={showAdd} onOpenChange={setShowAdd}>
        <DialogContent>
          <DialogHeader><DialogTitle>New Group</DialogTitle></DialogHeader>
          <GroupForm onSuccess={() => setShowAdd(false)} onCancel={() => setShowAdd(false)} />
        </DialogContent>
      </Dialog>
      <Dialog open={!!editGroup} onOpenChange={(o) => !o && setEditGroup(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle>Edit Group</DialogTitle></DialogHeader>
          {editGroup && <GroupForm group={editGroup} onSuccess={() => setEditGroup(null)} onCancel={() => setEditGroup(null)} />}
        </DialogContent>
      </Dialog>
      <Sheet open={!!detailGroup} onOpenChange={(o) => !o && setDetailGroup(null)}>
        <SheetContent>
          <SheetHeader><SheetTitle>{detailGroup?.name}</SheetTitle></SheetHeader>
          <div className="mt-6">
            {detailGroup && <GroupDetailPanel group={detailGroup} />}
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}
