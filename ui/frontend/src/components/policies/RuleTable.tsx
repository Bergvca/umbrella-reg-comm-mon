import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog";
import { useRules, useDeleteRule } from "@/hooks/usePolicies";
import { RuleForm } from "./RuleForm";
import type { RuleOut } from "@/lib/types";

interface RuleTableProps {
  policyId: string;
  canEdit: boolean;
}

export function RuleTable({ policyId, canEdit }: RuleTableProps) {
  const { data: rulesData, isLoading } = useRules(policyId);
  const rules = rulesData?.items;
  const deleteMutation = useDeleteRule(policyId);
  const [editRule, setEditRule] = useState<RuleOut | null>(null);
  const [showAdd, setShowAdd] = useState(false);

  if (isLoading) return <p className="text-sm text-muted-foreground">Loading rules…</p>;
  if (!rules?.length && !canEdit) return <p className="text-sm text-muted-foreground">No rules defined.</p>;

  return (
    <div className="space-y-2">
      {rules?.map((rule) => (
        <div key={rule.id} className="flex items-center gap-3 border rounded p-3 text-sm">
          <Badge variant="outline">{rule.severity}</Badge>
          <span className="flex-1 font-medium">{rule.name}</span>
          {rule.description && <span className="text-muted-foreground text-xs">{rule.description}</span>}
          {canEdit && (
            <div className="flex gap-1">
              <Button size="sm" variant="ghost" onClick={() => setEditRule(rule)}>Edit</Button>
              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button size="sm" variant="ghost" className="text-destructive hover:text-destructive">Delete</Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>Delete rule?</AlertDialogTitle>
                    <AlertDialogDescription>This cannot be undone.</AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>Cancel</AlertDialogCancel>
                    <AlertDialogAction onClick={() => deleteMutation.mutate(rule.id)}>Delete</AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            </div>
          )}
        </div>
      ))}
      {canEdit && (
        <Button size="sm" variant="outline" onClick={() => setShowAdd(true)}>+ Add Rule</Button>
      )}
      <Dialog open={showAdd} onOpenChange={setShowAdd}>
        <DialogContent>
          <DialogHeader><DialogTitle>Add Rule</DialogTitle></DialogHeader>
          <RuleForm policyId={policyId} onSuccess={() => setShowAdd(false)} onCancel={() => setShowAdd(false)} />
        </DialogContent>
      </Dialog>
      <Dialog open={!!editRule} onOpenChange={(o) => !o && setEditRule(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle>Edit Rule</DialogTitle></DialogHeader>
          {editRule && (
            <RuleForm policyId={policyId} rule={editRule} onSuccess={() => setEditRule(null)} onCancel={() => setEditRule(null)} />
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
