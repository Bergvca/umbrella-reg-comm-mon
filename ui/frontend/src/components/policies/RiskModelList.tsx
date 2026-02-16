import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { useRiskModels } from "@/hooks/useRiskModels";
import { RiskModelForm } from "./RiskModelForm";
import type { RiskModelDetail } from "@/lib/types";

interface RiskModelListProps {
  canEdit: boolean;
}

export function RiskModelList({ canEdit }: RiskModelListProps) {
  const { data: models, isLoading } = useRiskModels();
  const [showAdd, setShowAdd] = useState(false);
  const [editModel, setEditModel] = useState<RiskModelDetail | null>(null);

  if (isLoading) return <Skeleton className="h-24 w-full" />;

  return (
    <div className="space-y-3">
      {canEdit && (
        <div className="flex justify-end">
          <Button onClick={() => setShowAdd(true)}>+ Add Risk Model</Button>
        </div>
      )}
      {!models?.items?.length && <p className="text-sm text-muted-foreground">No risk models defined.</p>}
      <div className="space-y-2">
        {models?.items?.map((m) => (
          <div key={m.id} className="border rounded-lg p-4 space-y-1">
            <div className="flex items-center justify-between">
              <span className="font-medium">{m.name}</span>
              {canEdit && (
                <Button size="sm" variant="outline" onClick={() => setEditModel(m)}>Edit</Button>
              )}
            </div>
            {m.description && <p className="text-sm text-muted-foreground">{m.description}</p>}
          </div>
        ))}
      </div>
      <Dialog open={showAdd} onOpenChange={setShowAdd}>
        <DialogContent>
          <DialogHeader><DialogTitle>New Risk Model</DialogTitle></DialogHeader>
          <RiskModelForm onSuccess={() => setShowAdd(false)} onCancel={() => setShowAdd(false)} />
        </DialogContent>
      </Dialog>
      <Dialog open={!!editModel} onOpenChange={(o) => !o && setEditModel(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle>Edit Risk Model</DialogTitle></DialogHeader>
          {editModel && (
            <RiskModelForm model={editModel} onSuccess={() => setEditModel(null)} onCancel={() => setEditModel(null)} />
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
