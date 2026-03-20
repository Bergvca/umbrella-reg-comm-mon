import { useState } from "react";
import { toast } from "sonner";
import { Zap } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { usePolicies } from "@/hooks/usePolicies";
import { useRiskModels } from "@/hooks/useRiskModels";
import {
  useDefaultQuery,
  useCreateGenerationJob,
  useGenerationJob,
} from "@/hooks/useAlertGeneration";
import type { GenerationScopeType } from "@/lib/types";

type Step = "scope" | "query" | "confirm" | "progress";

export function GenerateAlertsDialog() {
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState<Step>("scope");
  const [scopeType, setScopeType] = useState<GenerationScopeType>("all");
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [kql, setKql] = useState<string>("");
  const [jobId, setJobId] = useState<string | null>(null);

  const { data: defaultQueryData } = useDefaultQuery();
  const { data: policies } = usePolicies({ is_active: true });
  const { data: riskModels } = useRiskModels({ is_active: true });
  const createJob = useCreateGenerationJob();
  const { data: job } = useGenerationJob(jobId);
  const qc = useQueryClient();

  function handleOpenChange(value: boolean) {
    setOpen(value);
    if (!value) {
      // Reset state on close
      setStep("scope");
      setScopeType("all");
      setSelectedIds([]);
      setKql("");
      setJobId(null);
      createJob.reset();
    }
  }

  function handleScopeNext() {
    const defaultKql = defaultQueryData?.default_kql ?? "*";
    setKql(defaultKql);
    setStep("query");
  }

  function handleQueryNext() {
    setStep("confirm");
  }

  function handleBack() {
    if (step === "query") setStep("scope");
    else if (step === "confirm") setStep("query");
  }

  async function handleGenerate() {
    createJob.mutate(
      {
        scope_type: scopeType,
        scope_ids: scopeType !== "all" ? selectedIds : undefined,
        query_kql: kql || null,
      },
      {
        onSuccess: (data) => {
          setJobId(data.id);
          setStep("progress");
        },
      }
    );
  }

  function handleClose() {
    if (job?.status === "completed") {
      void qc.invalidateQueries({ queryKey: ["alerts"] });
      toast.success(`Generation complete: ${job.alerts_created} alerts created`);
    }
    handleOpenChange(false);
  }

  // Count rules for summary
  const scopeLabel =
    scopeType === "all"
      ? "all active policies"
      : scopeType === "policies"
        ? `${selectedIds.length} selected ${selectedIds.length === 1 ? "policy" : "policies"}`
        : `${selectedIds.length} selected risk ${selectedIds.length === 1 ? "model" : "models"}`;

  function toggleId(id: string) {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  }

  const jobStatusClass: Record<string, string> = {
    pending: "text-yellow-600 bg-yellow-50 border-yellow-200",
    running: "text-blue-600 bg-blue-50 border-blue-200",
    completed: "text-green-600 bg-green-50 border-green-200",
    failed: "text-red-600 bg-red-50 border-red-200",
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          <Zap className="h-4 w-4 mr-1.5" />
          Generate Alerts
        </Button>
      </DialogTrigger>

      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Generate Alerts</DialogTitle>
        </DialogHeader>

        {/* ── Step 1: Scope ── */}
        {step === "scope" && (
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Select the scope of policies to evaluate.
            </p>
            <div className="space-y-2">
              {(
                [
                  { value: "all", label: "All active policies" },
                  { value: "policies", label: "Selected policies" },
                  { value: "risk_models", label: "Selected risk models" },
                ] as { value: GenerationScopeType; label: string }[]
              ).map(({ value, label }) => (
                <label key={value} className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="scope_type"
                    value={value}
                    checked={scopeType === value}
                    onChange={() => {
                      setScopeType(value);
                      setSelectedIds([]);
                    }}
                  />
                  <span className="text-sm">{label}</span>
                </label>
              ))}
            </div>

            {/* Policy checklist */}
            {scopeType === "policies" && (
              <div className="border rounded-md max-h-48 overflow-y-auto p-2 space-y-1">
                {policies?.items.length === 0 && (
                  <p className="text-xs text-muted-foreground p-1">No active policies.</p>
                )}
                {policies?.items.map((p) => (
                  <label key={p.id} className="flex items-center gap-2 cursor-pointer p-1 hover:bg-muted rounded">
                    <input
                      type="checkbox"
                      checked={selectedIds.includes(p.id)}
                      onChange={() => toggleId(p.id)}
                    />
                    <span className="text-sm flex-1">{p.name}</span>
                    {p.is_active && (
                      <Badge variant="outline" className="text-green-600 bg-green-50 border-green-200 text-xs">
                        Active
                      </Badge>
                    )}
                  </label>
                ))}
              </div>
            )}

            {/* Risk model checklist */}
            {scopeType === "risk_models" && (
              <div className="border rounded-md max-h-48 overflow-y-auto p-2 space-y-1">
                {riskModels?.items.length === 0 && (
                  <p className="text-xs text-muted-foreground p-1">No active risk models.</p>
                )}
                {riskModels?.items.map((rm) => (
                  <label key={rm.id} className="flex items-center gap-2 cursor-pointer p-1 hover:bg-muted rounded">
                    <input
                      type="checkbox"
                      checked={selectedIds.includes(rm.id)}
                      onChange={() => toggleId(rm.id)}
                    />
                    <span className="text-sm flex-1">{rm.name}</span>
                    {rm.is_active && (
                      <Badge variant="outline" className="text-green-600 bg-green-50 border-green-200 text-xs">
                        Active
                      </Badge>
                    )}
                  </label>
                ))}
              </div>
            )}

            <div className="flex justify-end">
              <Button
                size="sm"
                onClick={handleScopeNext}
                disabled={scopeType !== "all" && selectedIds.length === 0}
              >
                Next
              </Button>
            </div>
          </div>
        )}

        {/* ── Step 2: KQL filter ── */}
        {step === "query" && (
          <div className="space-y-4">
            <div className="space-y-1">
              <Label>Message filter (KQL)</Label>
              <p className="text-xs text-muted-foreground">
                Controls which indexed messages are evaluated. Default: messages ingested since the
                last generation run.
              </p>
              <Textarea
                className="font-mono text-sm"
                rows={3}
                value={kql}
                onChange={(e) => setKql(e.target.value)}
                placeholder="*"
              />
            </div>
            <div className="flex justify-between">
              <Button variant="ghost" size="sm" onClick={handleBack}>
                Back
              </Button>
              <Button size="sm" onClick={handleQueryNext}>
                Next
              </Button>
            </div>
          </div>
        )}

        {/* ── Step 3: Confirm ── */}
        {step === "confirm" && (
          <div className="space-y-4">
            <div className="rounded-md border p-3 space-y-2 text-sm">
              <p>
                <span className="text-muted-foreground">Scope: </span>
                {scopeLabel}
              </p>
              <p>
                <span className="text-muted-foreground">KQL filter: </span>
                <code className="font-mono text-xs bg-muted px-1 py-0.5 rounded">{kql || "*"}</code>
              </p>
            </div>
            <p className="text-xs text-muted-foreground">
              Matching alerts will be created. Re-running against already-alerted messages is safe
              (idempotent).
            </p>
            <div className="flex justify-between">
              <Button variant="ghost" size="sm" onClick={handleBack}>
                Back
              </Button>
              <Button
                size="sm"
                onClick={() => void handleGenerate()}
                disabled={createJob.isPending}
              >
                {createJob.isPending ? "Starting…" : "Generate"}
              </Button>
            </div>
            {createJob.isError && (
              <p className="text-xs text-red-600">
                Failed to start generation job. A job may already be running.
              </p>
            )}
          </div>
        )}

        {/* ── Step 4: Progress ── */}
        {step === "progress" && job && (
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">Status:</span>
              <Badge
                variant="outline"
                className={jobStatusClass[job.status] ?? ""}
              >
                {job.status}
              </Badge>
            </div>

            <div className="rounded-md border p-3 space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Rules evaluated</span>
                <span>{job.rules_evaluated}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Documents scanned</span>
                <span>{job.documents_scanned.toLocaleString()}</span>
              </div>
              <div className="flex justify-between font-medium">
                <span>Alerts created</span>
                <span>{job.alerts_created}</span>
              </div>
            </div>

            {job.query_kql_resolved && (
              <p className="text-xs text-muted-foreground">
                KQL:{" "}
                <code className="font-mono bg-muted px-1 py-0.5 rounded">
                  {job.query_kql_resolved}
                </code>
              </p>
            )}

            {job.error_message && (
              <p className="text-xs text-red-600">Error: {job.error_message}</p>
            )}

            {(job.status === "completed" || job.status === "failed") && (
              <div className="flex justify-end">
                <Button size="sm" onClick={handleClose}>
                  Close
                </Button>
              </div>
            )}
          </div>
        )}

        {/* Loading state while job not fetched yet */}
        {step === "progress" && !job && (
          <p className="text-sm text-muted-foreground">Starting generation job…</p>
        )}
      </DialogContent>
    </Dialog>
  );
}
