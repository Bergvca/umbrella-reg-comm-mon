import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from "react";
import { toast } from "sonner";
import { Zap } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, } from "@/components/ui/dialog";
import { usePolicies } from "@/hooks/usePolicies";
import { useRiskModels } from "@/hooks/useRiskModels";
import { useDefaultQuery, useCreateGenerationJob, useGenerationJob, } from "@/hooks/useAlertGeneration";
export function GenerateAlertsDialog() {
    const [open, setOpen] = useState(false);
    const [step, setStep] = useState("scope");
    const [scopeType, setScopeType] = useState("all");
    const [selectedIds, setSelectedIds] = useState([]);
    const [kql, setKql] = useState("");
    const [jobId, setJobId] = useState(null);
    const { data: defaultQueryData } = useDefaultQuery();
    const { data: policies } = usePolicies({ is_active: true });
    const { data: riskModels } = useRiskModels({ is_active: true });
    const createJob = useCreateGenerationJob();
    const { data: job } = useGenerationJob(jobId);
    const qc = useQueryClient();
    function handleOpenChange(value) {
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
        if (step === "query")
            setStep("scope");
        else if (step === "confirm")
            setStep("query");
    }
    async function handleGenerate() {
        createJob.mutate({
            scope_type: scopeType,
            scope_ids: scopeType !== "all" ? selectedIds : undefined,
            query_kql: kql || null,
        }, {
            onSuccess: (data) => {
                setJobId(data.id);
                setStep("progress");
            },
        });
    }
    function handleClose() {
        if (job?.status === "completed") {
            void qc.invalidateQueries({ queryKey: ["alerts"] });
            toast.success(`Generation complete: ${job.alerts_created} alerts created`);
        }
        handleOpenChange(false);
    }
    // Count rules for summary
    const scopeLabel = scopeType === "all"
        ? "all active policies"
        : scopeType === "policies"
            ? `${selectedIds.length} selected ${selectedIds.length === 1 ? "policy" : "policies"}`
            : `${selectedIds.length} selected risk ${selectedIds.length === 1 ? "model" : "models"}`;
    function toggleId(id) {
        setSelectedIds((prev) => prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]);
    }
    const jobStatusClass = {
        pending: "text-yellow-600 bg-yellow-50 border-yellow-200",
        running: "text-blue-600 bg-blue-50 border-blue-200",
        completed: "text-green-600 bg-green-50 border-green-200",
        failed: "text-red-600 bg-red-50 border-red-200",
    };
    return (_jsxs(Dialog, { open: open, onOpenChange: handleOpenChange, children: [_jsx(DialogTrigger, { asChild: true, children: _jsxs(Button, { variant: "outline", size: "sm", children: [_jsx(Zap, { className: "h-4 w-4 mr-1.5" }), "Generate Alerts"] }) }), _jsxs(DialogContent, { className: "max-w-lg", children: [_jsx(DialogHeader, { children: _jsx(DialogTitle, { children: "Generate Alerts" }) }), step === "scope" && (_jsxs("div", { className: "space-y-4", children: [_jsx("p", { className: "text-sm text-muted-foreground", children: "Select the scope of policies to evaluate." }), _jsx("div", { className: "space-y-2", children: [
                                    { value: "all", label: "All active policies" },
                                    { value: "policies", label: "Selected policies" },
                                    { value: "risk_models", label: "Selected risk models" },
                                ].map(({ value, label }) => (_jsxs("label", { className: "flex items-center gap-2 cursor-pointer", children: [_jsx("input", { type: "radio", name: "scope_type", value: value, checked: scopeType === value, onChange: () => {
                                                setScopeType(value);
                                                setSelectedIds([]);
                                            } }), _jsx("span", { className: "text-sm", children: label })] }, value))) }), scopeType === "policies" && (_jsxs("div", { className: "border rounded-md max-h-48 overflow-y-auto p-2 space-y-1", children: [policies?.items.length === 0 && (_jsx("p", { className: "text-xs text-muted-foreground p-1", children: "No active policies." })), policies?.items.map((p) => (_jsxs("label", { className: "flex items-center gap-2 cursor-pointer p-1 hover:bg-muted rounded", children: [_jsx("input", { type: "checkbox", checked: selectedIds.includes(p.id), onChange: () => toggleId(p.id) }), _jsx("span", { className: "text-sm flex-1", children: p.name }), p.is_active && (_jsx(Badge, { variant: "outline", className: "text-green-600 bg-green-50 border-green-200 text-xs", children: "Active" }))] }, p.id)))] })), scopeType === "risk_models" && (_jsxs("div", { className: "border rounded-md max-h-48 overflow-y-auto p-2 space-y-1", children: [riskModels?.items.length === 0 && (_jsx("p", { className: "text-xs text-muted-foreground p-1", children: "No active risk models." })), riskModels?.items.map((rm) => (_jsxs("label", { className: "flex items-center gap-2 cursor-pointer p-1 hover:bg-muted rounded", children: [_jsx("input", { type: "checkbox", checked: selectedIds.includes(rm.id), onChange: () => toggleId(rm.id) }), _jsx("span", { className: "text-sm flex-1", children: rm.name }), rm.is_active && (_jsx(Badge, { variant: "outline", className: "text-green-600 bg-green-50 border-green-200 text-xs", children: "Active" }))] }, rm.id)))] })), _jsx("div", { className: "flex justify-end", children: _jsx(Button, { size: "sm", onClick: handleScopeNext, disabled: scopeType !== "all" && selectedIds.length === 0, children: "Next" }) })] })), step === "query" && (_jsxs("div", { className: "space-y-4", children: [_jsxs("div", { className: "space-y-1", children: [_jsx(Label, { children: "Message filter (KQL)" }), _jsx("p", { className: "text-xs text-muted-foreground", children: "Controls which indexed messages are evaluated. Default: messages ingested since the last generation run." }), _jsx(Textarea, { className: "font-mono text-sm", rows: 3, value: kql, onChange: (e) => setKql(e.target.value), placeholder: "*" })] }), _jsxs("div", { className: "flex justify-between", children: [_jsx(Button, { variant: "ghost", size: "sm", onClick: handleBack, children: "Back" }), _jsx(Button, { size: "sm", onClick: handleQueryNext, children: "Next" })] })] })), step === "confirm" && (_jsxs("div", { className: "space-y-4", children: [_jsxs("div", { className: "rounded-md border p-3 space-y-2 text-sm", children: [_jsxs("p", { children: [_jsx("span", { className: "text-muted-foreground", children: "Scope: " }), scopeLabel] }), _jsxs("p", { children: [_jsx("span", { className: "text-muted-foreground", children: "KQL filter: " }), _jsx("code", { className: "font-mono text-xs bg-muted px-1 py-0.5 rounded", children: kql || "*" })] })] }), _jsx("p", { className: "text-xs text-muted-foreground", children: "Matching alerts will be created. Re-running against already-alerted messages is safe (idempotent)." }), _jsxs("div", { className: "flex justify-between", children: [_jsx(Button, { variant: "ghost", size: "sm", onClick: handleBack, children: "Back" }), _jsx(Button, { size: "sm", onClick: () => void handleGenerate(), disabled: createJob.isPending, children: createJob.isPending ? "Starting…" : "Generate" })] }), createJob.isError && (_jsx("p", { className: "text-xs text-red-600", children: "Failed to start generation job. A job may already be running." }))] })), step === "progress" && job && (_jsxs("div", { className: "space-y-4", children: [_jsxs("div", { className: "flex items-center gap-2", children: [_jsx("span", { className: "text-sm text-muted-foreground", children: "Status:" }), _jsx(Badge, { variant: "outline", className: jobStatusClass[job.status] ?? "", children: job.status })] }), _jsxs("div", { className: "rounded-md border p-3 space-y-2 text-sm", children: [_jsxs("div", { className: "flex justify-between", children: [_jsx("span", { className: "text-muted-foreground", children: "Rules evaluated" }), _jsx("span", { children: job.rules_evaluated })] }), _jsxs("div", { className: "flex justify-between", children: [_jsx("span", { className: "text-muted-foreground", children: "Documents scanned" }), _jsx("span", { children: job.documents_scanned.toLocaleString() })] }), _jsxs("div", { className: "flex justify-between font-medium", children: [_jsx("span", { children: "Alerts created" }), _jsx("span", { children: job.alerts_created })] })] }), job.query_kql_resolved && (_jsxs("p", { className: "text-xs text-muted-foreground", children: ["KQL:", " ", _jsx("code", { className: "font-mono bg-muted px-1 py-0.5 rounded", children: job.query_kql_resolved })] })), job.error_message && (_jsxs("p", { className: "text-xs text-red-600", children: ["Error: ", job.error_message] })), (job.status === "completed" || job.status === "failed") && (_jsx("div", { className: "flex justify-end", children: _jsx(Button, { size: "sm", onClick: handleClose, children: "Close" }) }))] })), step === "progress" && !job && (_jsx("p", { className: "text-sm text-muted-foreground", children: "Starting generation job\u2026" }))] })] }));
}
