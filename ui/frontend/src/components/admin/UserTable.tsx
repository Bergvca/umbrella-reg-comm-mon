import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { useUsers } from "@/hooks/useUsers";
import { UserForm } from "./UserForm";
import { UserGroupManager } from "./UserGroupManager";
import type { UserOut } from "@/lib/types";

export function UserTable() {
  const { data: users, isLoading } = useUsers();
  const [editUser, setEditUser] = useState<UserOut | null>(null);
  const [manageUser, setManageUser] = useState<UserOut | null>(null);
  const [showAdd, setShowAdd] = useState(false);

  if (isLoading) return <Skeleton className="h-48 w-full" />;

  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <Button onClick={() => setShowAdd(true)}>+ Add User</Button>
      </div>
      <div className="border rounded-lg divide-y">
        {!users?.items?.length && (
          <p className="p-4 text-sm text-muted-foreground">No users found.</p>
        )}
        {users?.items?.map((u) => (
          <div key={u.id} className="flex items-center gap-3 p-3">
            <div className="flex-1">
              <p className="text-sm font-medium">{u.full_name ?? u.email}</p>
              <p className="text-xs text-muted-foreground">{u.email}</p>
            </div>
            {u.is_active ? (
              <Badge variant="outline" className="text-green-600 border-green-300">Active</Badge>
            ) : (
              <Badge variant="outline" className="text-muted-foreground">Inactive</Badge>
            )}
            <Button size="sm" variant="ghost" onClick={() => setManageUser(u)}>Groups</Button>
            <Button size="sm" variant="outline" onClick={() => setEditUser(u)}>Edit</Button>
          </div>
        ))}
      </div>
      <Dialog open={showAdd} onOpenChange={setShowAdd}>
        <DialogContent>
          <DialogHeader><DialogTitle>New User</DialogTitle></DialogHeader>
          <UserForm onSuccess={() => setShowAdd(false)} onCancel={() => setShowAdd(false)} />
        </DialogContent>
      </Dialog>
      <Dialog open={!!editUser} onOpenChange={(o) => !o && setEditUser(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle>Edit User</DialogTitle></DialogHeader>
          {editUser && <UserForm user={editUser} onSuccess={() => setEditUser(null)} onCancel={() => setEditUser(null)} />}
        </DialogContent>
      </Dialog>
      <Sheet open={!!manageUser} onOpenChange={(o) => !o && setManageUser(null)}>
        <SheetContent>
          <SheetHeader><SheetTitle>{manageUser?.full_name ?? manageUser?.email}</SheetTitle></SheetHeader>
          <div className="mt-6">
            {manageUser && <UserGroupManager userId={manageUser.id} />}
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}
