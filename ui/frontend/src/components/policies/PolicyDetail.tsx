import { useState } from "react";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { RuleTable } from "./RuleTable";
import { GroupPolicyManager } from "./GroupPolicyManager";
import { PolicyForm } from "./PolicyForm";
import type { PolicyDetail as PolicyDetailType } from "@/lib/types";

interface PolicyDetailProps {
  policy: PolicyDetailType;
  canEdit: boolean;
}

export function PolicyDetail({ policy, canEdit }: PolicyDetailProps) {
  const [showEdit, setShowEdit] = useState(false);

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between pb-3 border-b">
        <div>
          <h3 className="font-semibold text-lg">{policy.name}</h3>
          {policy.description && <p className="text-sm text-muted-foreground mt-1">{policy.description}</p>}
          {policy.risk_model_id && (
            <Badge variant="secondary" className="mt-2">Risk Model #{policy.risk_model_id}</Badge>
          )}
        </div>
        {canEdit && (
          <Button size="sm" variant="outline" onClick={() => setShowEdit(true)}>Edit Policy</Button>
        )}
      </div>

      <Accordion type="multiple" defaultValue={["rules", "groups"]}>
        <AccordionItem value="rules">
          <AccordionTrigger>Rules</AccordionTrigger>
          <AccordionContent>
            <RuleTable policyId={policy.id} canEdit={canEdit} />
          </AccordionContent>
        </AccordionItem>
        <AccordionItem value="groups">
          <AccordionTrigger>Assigned Groups</AccordionTrigger>
          <AccordionContent>
            <GroupPolicyManager policyId={policy.id} canEdit={canEdit} />
          </AccordionContent>
        </AccordionItem>
      </Accordion>

      <Dialog open={showEdit} onOpenChange={setShowEdit}>
        <DialogContent>
          <DialogHeader><DialogTitle>Edit Policy</DialogTitle></DialogHeader>
          <PolicyForm policy={policy} onSuccess={() => setShowEdit(false)} onCancel={() => setShowEdit(false)} />
        </DialogContent>
      </Dialog>
    </div>
  );
}
