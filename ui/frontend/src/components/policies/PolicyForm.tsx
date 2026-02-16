import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useRiskModels } from "@/hooks/useRiskModels";
import { useCreatePolicy, useUpdatePolicy } from "@/hooks/usePolicies";
import type { PolicyDetail } from "@/lib/types";

interface PolicyFormProps {
  policy?: PolicyDetail;
  onSuccess: () => void;
  onCancel: () => void;
}

export function PolicyForm({ policy, onSuccess, onCancel }: PolicyFormProps) {
  const [name, setName] = useState(policy?.name ?? "");
  const [description, setDescription] = useState(policy?.description ?? "");
  const [riskModelId, setRiskModelId] = useState(policy?.risk_model_id ?? "none");
  const { data: riskModels } = useRiskModels();
  const createMutation = useCreatePolicy();
  const updateMutation = useUpdatePolicy();

  const isPending = createMutation.isPending || updateMutation.isPending;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (policy) {
      updateMutation.mutate({ id: policy.id, name, description: description || undefined }, { onSuccess });
    } else {
      createMutation.mutate({ risk_model_id: riskModelId === "none" ? "" : riskModelId, name, description: description || undefined }, { onSuccess });
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-1">
        <Label>Name</Label>
        <Input value={name} onChange={(e) => setName(e.target.value)} required />
      </div>
      <div className="space-y-1">
        <Label>Description</Label>
        <Textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} />
      </div>
      <div className="space-y-1">
        <Label>Risk Model</Label>
        <Select value={riskModelId} onValueChange={setRiskModelId}>
          <SelectTrigger><SelectValue placeholder="None" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="none">None</SelectItem>
            {riskModels?.items?.map((m) => (
              <SelectItem key={m.id} value={m.id}>{m.name}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="flex gap-2 justify-end">
        <Button type="button" variant="outline" onClick={onCancel}>Cancel</Button>
        <Button type="submit" disabled={isPending}>{isPending ? "Saving…" : "Save"}</Button>
      </div>
    </form>
  );
}
