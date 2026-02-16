import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useCreateRule, useUpdateRule } from "@/hooks/usePolicies";
import type { RuleOut } from "@/lib/types";

interface RuleFormProps {
  policyId: string;
  rule?: RuleOut;
  onSuccess: () => void;
  onCancel: () => void;
}

export function RuleForm({ policyId, rule, onSuccess, onCancel }: RuleFormProps) {
  const [name, setName] = useState(rule?.name ?? "");
  const [description, setDescription] = useState(rule?.description ?? "");
  const [severity, setSeverity] = useState<string>(rule?.severity ?? "low");
  const [kql, setKql] = useState(rule?.kql ?? "");
  const createMutation = useCreateRule(policyId);
  const updateMutation = useUpdateRule(policyId);

  const isPending = createMutation.isPending || updateMutation.isPending;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const payload = { name, description: description || undefined, kql, severity };
    if (rule) {
      updateMutation.mutate({ ruleId: rule.id, ...payload }, { onSuccess });
    } else {
      createMutation.mutate(payload, { onSuccess });
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
        <Textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={2} />
      </div>
      <div className="space-y-1">
        <Label>Severity</Label>
        <Select value={severity} onValueChange={setSeverity}>
          <SelectTrigger><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="low">Low</SelectItem>
            <SelectItem value="medium">Medium</SelectItem>
            <SelectItem value="high">High</SelectItem>
            <SelectItem value="critical">Critical</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div className="space-y-1">
        <Label>KQL Expression</Label>
        <Textarea
          value={kql}
          onChange={(e) => setKql(e.target.value)}
          rows={4}
          className="font-mono text-sm"
          placeholder="e.g. body_text: (insider OR confidential)"
        />
      </div>
      <div className="flex gap-2 justify-end">
        <Button type="button" variant="outline" onClick={onCancel}>Cancel</Button>
        <Button type="submit" disabled={isPending}>{isPending ? "Saving…" : "Save"}</Button>
      </div>
    </form>
  );
}
