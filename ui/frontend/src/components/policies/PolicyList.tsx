import { useState } from "react";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { usePolicies } from "@/hooks/usePolicies";
import { PolicyDetail } from "./PolicyDetail";
import { PolicyForm } from "./PolicyForm";

interface PolicyListProps {
  canEdit: boolean;
}

export function PolicyList({ canEdit }: PolicyListProps) {
  const { data: policies, isLoading } = usePolicies();
  const [showAdd, setShowAdd] = useState(false);

  if (isLoading) return <Skeleton className="h-32 w-full" />;

  return (
    <div className="space-y-4">
      {canEdit && (
        <div className="flex justify-end">
          <Button onClick={() => setShowAdd(true)}>+ Add Policy</Button>
        </div>
      )}
      {!policies?.items?.length && <p className="text-sm text-muted-foreground">No policies defined.</p>}
      <Accordion type="single" collapsible className="space-y-2">
        {policies?.items?.map((policy) => (
          <AccordionItem key={policy.id} value={String(policy.id)} className="border rounded-lg px-4">
            <AccordionTrigger className="hover:no-underline">
              <span className="font-medium">{policy.name}</span>
            </AccordionTrigger>
            <AccordionContent>
              <PolicyDetail policy={policy} canEdit={canEdit} />
            </AccordionContent>
          </AccordionItem>
        ))}
      </Accordion>
      <Dialog open={showAdd} onOpenChange={setShowAdd}>
        <DialogContent>
          <DialogHeader><DialogTitle>New Policy</DialogTitle></DialogHeader>
          <PolicyForm onSuccess={() => setShowAdd(false)} onCancel={() => setShowAdd(false)} />
        </DialogContent>
      </Dialog>
    </div>
  );
}
