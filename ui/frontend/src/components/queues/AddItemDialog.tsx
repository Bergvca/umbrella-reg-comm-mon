import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { useAddItemToBatch } from "@/hooks/useQueues";

interface AddItemDialogProps {
  queueId: string;
  batchId: string;
}

export function AddItemDialog({ queueId, batchId }: AddItemDialogProps) {
  const [open, setOpen] = useState(false);
  const [alertId, setAlertId] = useState("");
  const [position, setPosition] = useState("0");
  const mutation = useAddItemToBatch(queueId, batchId);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    mutation.mutate(
      { alert_id: alertId, position: parseInt(position, 10) },
      {
        onSuccess: () => {
          setOpen(false);
          setAlertId("");
          setPosition("0");
        },
      }
    );
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" variant="ghost">+ Add Item</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader><DialogTitle>Add Item to Batch</DialogTitle></DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1">
            <Label>Alert ID</Label>
            <Input value={alertId} onChange={(e) => setAlertId(e.target.value)} required placeholder="Alert ID" />
          </div>
          <div className="space-y-1">
            <Label>Position</Label>
            <Input
              type="number"
              min={0}
              value={position}
              onChange={(e) => setPosition(e.target.value)}
              required
            />
          </div>
          <div className="flex gap-2 justify-end">
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
            <Button type="submit" disabled={mutation.isPending}>{mutation.isPending ? "Adding…" : "Add"}</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
