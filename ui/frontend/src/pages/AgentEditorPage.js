import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router";
import { toast } from "sonner";
import { useAgent, useAgentModels, useAgentTools, useDataSourceOptions, useCreateAgent, useUpdateAgent } from "@/hooks/useAgents";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue, } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Plus, X } from "lucide-react";
const STEPS = ["identity", "model", "instructions", "tools", "schema", "review"];
const STEP_LABELS = {
    identity: "Identity",
    model: "Model & Behavior",
    instructions: "Instructions",
    tools: "Tools & Data Sources",
    schema: "Output Schema",
    review: "Review & Save",
};
const DEFAULT_FORM = {
    name: "",
    description: "",
    model_id: "",
    temperature: 0.0,
    max_iterations: 10,
    system_prompt: "",
    selected_tool_ids: [],
    data_sources: [],
    structured_output: false,
    output_schema_text: "",
};
function validateOutputSchema(text) {
    if (!text.trim())
        return null;
    try {
        return JSON.parse(text);
    }
    catch {
        return undefined;
    }
}
export function AgentEditorPage() {
    const { id } = useParams();
    const navigate = useNavigate();
    const isEdit = !!id;
    const { data: existing, isLoading: loadingExisting } = useAgent(id ?? "");
    const { data: modelsData, isLoading: loadingModels } = useAgentModels();
    const { data: toolsData } = useAgentTools();
    const { data: dsOptions } = useDataSourceOptions();
    const createAgent = useCreateAgent();
    const updateAgent = useUpdateAgent();
    const [step, setStep] = useState("identity");
    const [form, setForm] = useState(DEFAULT_FORM);
    const [schemaError, setSchemaError] = useState(null);
    const [newDsType, setNewDsType] = useState("elasticsearch");
    const [newDsId, setNewDsId] = useState("");
    // Pre-fill form when editing
    useEffect(() => {
        if (existing && isEdit) {
            setForm({
                name: existing.name,
                description: existing.description ?? "",
                model_id: existing.model.id,
                temperature: existing.temperature,
                max_iterations: existing.max_iterations,
                system_prompt: existing.system_prompt,
                selected_tool_ids: existing.tools.map((t) => t.id),
                data_sources: existing.data_sources.map((ds) => ({
                    source_type: ds.source_type,
                    source_identifier: ds.source_identifier,
                })),
                structured_output: existing.output_schema != null,
                output_schema_text: existing.output_schema
                    ? JSON.stringify(existing.output_schema, null, 2)
                    : "",
            });
        }
    }, [existing, isEdit]);
    function update(key, value) {
        setForm((prev) => ({ ...prev, [key]: value }));
    }
    function toggleTool(toolId) {
        setForm((prev) => ({
            ...prev,
            selected_tool_ids: prev.selected_tool_ids.includes(toolId)
                ? prev.selected_tool_ids.filter((id) => id !== toolId)
                : [...prev.selected_tool_ids, toolId],
        }));
    }
    function addDataSource() {
        if (!newDsId.trim())
            return;
        setForm((prev) => ({
            ...prev,
            data_sources: [
                ...prev.data_sources,
                { source_type: newDsType, source_identifier: newDsId.trim() },
            ],
        }));
        setNewDsId("");
    }
    function removeDataSource(index) {
        setForm((prev) => ({
            ...prev,
            data_sources: prev.data_sources.filter((_, i) => i !== index),
        }));
    }
    const currentStepIndex = STEPS.indexOf(step);
    function goNext() {
        if (step === "schema") {
            if (form.structured_output && form.output_schema_text.trim()) {
                const parsed = validateOutputSchema(form.output_schema_text);
                if (parsed === undefined) {
                    setSchemaError("Invalid JSON");
                    return;
                }
            }
            setSchemaError(null);
        }
        if (currentStepIndex < STEPS.length - 1) {
            setStep(STEPS[currentStepIndex + 1]);
        }
    }
    function goBack() {
        if (currentStepIndex > 0) {
            setStep(STEPS[currentStepIndex - 1]);
        }
    }
    function handleSave() {
        let output_schema = null;
        if (form.structured_output && form.output_schema_text.trim()) {
            const parsed = validateOutputSchema(form.output_schema_text);
            if (parsed === undefined) {
                setSchemaError("Invalid JSON");
                setStep("schema");
                return;
            }
            output_schema = parsed;
        }
        const payload = {
            name: form.name,
            description: form.description || undefined,
            model_id: form.model_id,
            system_prompt: form.system_prompt,
            temperature: form.temperature,
            max_iterations: form.max_iterations,
            output_schema,
            tool_ids: form.selected_tool_ids,
            data_sources: form.data_sources,
        };
        if (isEdit) {
            updateAgent.mutate({ id: id, body: payload }, {
                onSuccess: (agent) => {
                    toast.success("Agent updated");
                    void navigate(`/agents/${agent.id}`);
                },
                onError: () => toast.error("Failed to update agent"),
            });
        }
        else {
            createAgent.mutate(payload, {
                onSuccess: (agent) => {
                    toast.success("Agent created");
                    void navigate(`/agents/${agent.id}`);
                },
                onError: () => toast.error("Failed to create agent"),
            });
        }
    }
    if (isEdit && loadingExisting) {
        return (_jsxs("div", { className: "p-6 space-y-4", children: [_jsx(Skeleton, { className: "h-8 w-48" }), _jsx(Skeleton, { className: "h-64 w-full" })] }));
    }
    const isSaving = createAgent.isPending || updateAgent.isPending;
    const models = modelsData?.items ?? [];
    const tools = toolsData?.items ?? [];
    return (_jsxs("div", { className: "p-6 max-w-2xl space-y-6", children: [_jsxs("div", { className: "space-y-1", children: [_jsx("h1", { className: "text-2xl font-semibold", children: isEdit ? "Edit Agent" : "New Agent" }), _jsx("div", { className: "flex items-center gap-1 text-sm", children: STEPS.map((s, i) => (_jsxs("span", { className: "flex items-center gap-1", children: [i > 0 && _jsx("span", { className: "text-muted-foreground", children: "/" }), _jsx("span", { className: s === step ? "font-medium text-foreground" : "text-muted-foreground", children: STEP_LABELS[s] })] }, s))) })] }), _jsxs(Card, { children: [_jsx(CardHeader, { children: _jsx(CardTitle, { children: STEP_LABELS[step] }) }), _jsxs(CardContent, { className: "space-y-4", children: [step === "identity" && (_jsxs(_Fragment, { children: [_jsxs("div", { className: "space-y-1", children: [_jsxs(Label, { children: ["Name ", _jsx("span", { className: "text-destructive", children: "*" })] }), _jsx(Input, { value: form.name, onChange: (e) => update("name", e.target.value), placeholder: "e.g. Trade Surveillance Agent" })] }), _jsxs("div", { className: "space-y-1", children: [_jsx(Label, { children: "Description" }), _jsx(Input, { value: form.description, onChange: (e) => update("description", e.target.value), placeholder: "Optional description" })] })] })), step === "model" && (_jsxs(_Fragment, { children: [_jsxs("div", { className: "space-y-1", children: [_jsxs(Label, { children: ["Model ", _jsx("span", { className: "text-destructive", children: "*" })] }), loadingModels ? (_jsx(Skeleton, { className: "h-10 w-full" })) : (_jsxs(Select, { value: form.model_id, onValueChange: (v) => update("model_id", v), children: [_jsx(SelectTrigger, { children: _jsx(SelectValue, { placeholder: "Select a model" }) }), _jsx(SelectContent, { children: models.map((m) => (_jsxs(SelectItem, { value: m.id, children: [m.name, " (", m.provider, ")"] }, m.id))) })] }))] }), _jsxs("div", { className: "space-y-1", children: [_jsxs(Label, { children: ["Temperature (", form.temperature.toFixed(1), ")"] }), _jsx("input", { type: "range", min: 0, max: 1, step: 0.1, value: form.temperature, onChange: (e) => update("temperature", Number(e.target.value)), className: "w-full" }), _jsxs("div", { className: "flex justify-between text-xs text-muted-foreground", children: [_jsx("span", { children: "0.0 (precise)" }), _jsx("span", { children: "1.0 (creative)" })] })] }), _jsxs("div", { className: "space-y-1", children: [_jsx(Label, { children: "Max Iterations" }), _jsx(Input, { type: "number", min: 1, max: 50, value: form.max_iterations, onChange: (e) => update("max_iterations", Number(e.target.value)) })] })] })), step === "instructions" && (_jsxs("div", { className: "space-y-1", children: [_jsxs(Label, { children: ["System Prompt ", _jsx("span", { className: "text-destructive", children: "*" })] }), _jsx(Textarea, { rows: 10, value: form.system_prompt, onChange: (e) => update("system_prompt", e.target.value), placeholder: "You are an AI assistant specialized in...", className: "font-mono text-sm" })] })), step === "tools" && (_jsxs(_Fragment, { children: [_jsxs("div", { className: "space-y-2", children: [_jsx(Label, { children: "Tools" }), tools.length === 0 ? (_jsx("p", { className: "text-sm text-muted-foreground", children: "No tools available." })) : (_jsx("div", { className: "border rounded-md max-h-48 overflow-y-auto p-2 space-y-1", children: tools.map((tool) => (_jsxs("label", { className: "flex items-start gap-2 cursor-pointer p-1.5 hover:bg-muted rounded", children: [_jsx("input", { type: "checkbox", className: "mt-0.5", checked: form.selected_tool_ids.includes(tool.id), onChange: () => toggleTool(tool.id) }), _jsxs("div", { className: "flex-1 min-w-0", children: [_jsx("p", { className: "text-sm font-medium", children: tool.display_name }), _jsx("p", { className: "text-xs text-muted-foreground truncate", children: tool.description })] }), _jsx(Badge, { variant: "outline", className: "text-xs shrink-0", children: tool.category })] }, tool.id))) }))] }), _jsxs("div", { className: "space-y-2", children: [_jsx(Label, { children: "Data Sources" }), form.data_sources.length > 0 && (_jsx("div", { className: "space-y-2", children: form.data_sources.map((ds, i) => (_jsxs("div", { className: "flex items-center gap-2 text-sm", children: [_jsx(Badge, { variant: "outline", children: ds.source_type }), _jsx("span", { className: "font-mono text-xs flex-1", children: ds.source_identifier }), _jsx(Button, { variant: "ghost", size: "icon", className: "h-6 w-6", onClick: () => removeDataSource(i), children: _jsx(X, { className: "h-3 w-3" }) })] }, i))) })), _jsxs("div", { className: "flex gap-2", children: [_jsxs(Select, { value: newDsType, onValueChange: (v) => {
                                                            setNewDsType(v);
                                                            setNewDsId("");
                                                        }, children: [_jsx(SelectTrigger, { className: "w-40", children: _jsx(SelectValue, {}) }), _jsxs(SelectContent, { children: [_jsx(SelectItem, { value: "elasticsearch", children: "Elasticsearch" }), _jsx(SelectItem, { value: "postgresql", children: "PostgreSQL" })] })] }), newDsType === "postgresql" ? (_jsxs(Select, { value: newDsId, onValueChange: (v) => setNewDsId(v), children: [_jsx(SelectTrigger, { className: "flex-1", children: _jsx(SelectValue, { placeholder: "Select a table" }) }), _jsx(SelectContent, { children: (dsOptions?.postgresql_tables ?? []).map((t) => (_jsx(SelectItem, { value: t, children: t }, t))) })] })) : (_jsxs(_Fragment, { children: [_jsx(Input, { list: "es-index-options", value: newDsId, onChange: (e) => setNewDsId(e.target.value), placeholder: "Index name or pattern (e.g. messages-*)", className: "flex-1", onKeyDown: (e) => {
                                                                    if (e.key === "Enter") {
                                                                        e.preventDefault();
                                                                        addDataSource();
                                                                    }
                                                                } }), _jsx("datalist", { id: "es-index-options", children: (dsOptions?.elasticsearch_indices ?? []).map((idx) => (_jsx("option", { value: idx }, idx))) })] })), _jsx(Button, { variant: "outline", size: "icon", onClick: addDataSource, children: _jsx(Plus, { className: "h-4 w-4" }) })] })] })] })), step === "schema" && (_jsxs(_Fragment, { children: [_jsxs("div", { className: "flex items-center gap-2", children: [_jsx("input", { type: "checkbox", id: "structured-output", checked: form.structured_output, onChange: (e) => update("structured_output", e.target.checked) }), _jsx(Label, { htmlFor: "structured-output", children: "Enable structured output" })] }), form.structured_output && (_jsxs("div", { className: "space-y-1", children: [_jsx(Label, { children: "JSON Schema" }), _jsx(Textarea, { rows: 8, value: form.output_schema_text, onChange: (e) => {
                                                    update("output_schema_text", e.target.value);
                                                    setSchemaError(null);
                                                }, placeholder: '{"type": "object", "properties": {...}}', className: "font-mono text-sm" }), schemaError && (_jsx("p", { className: "text-xs text-destructive", children: schemaError }))] })), !form.structured_output && (_jsx("p", { className: "text-sm text-muted-foreground", children: "The agent will return free-form text output." }))] })), step === "review" && (_jsx("div", { className: "space-y-4 text-sm", children: _jsxs("div", { className: "rounded-md border p-3 space-y-3", children: [_jsxs("div", { children: [_jsx("span", { className: "text-muted-foreground", children: "Name: " }), _jsx("span", { className: "font-medium", children: form.name || "—" }), form.description && (_jsx("p", { className: "text-muted-foreground text-xs mt-0.5", children: form.description }))] }), _jsxs("div", { children: [_jsx("span", { className: "text-muted-foreground", children: "Model: " }), _jsx("span", { children: models.find((m) => m.id === form.model_id)?.name ?? "—" }), _jsxs("span", { className: "text-muted-foreground ml-2", children: ["(temp ", form.temperature.toFixed(1), ", ", form.max_iterations, " iterations)"] })] }), _jsxs("div", { children: [_jsx("p", { className: "text-muted-foreground mb-1", children: "System Prompt:" }), _jsx("pre", { className: "bg-muted rounded p-2 text-xs whitespace-pre-wrap max-h-24 overflow-auto", children: form.system_prompt || "—" })] }), _jsxs("div", { children: [_jsx("span", { className: "text-muted-foreground", children: "Tools: " }), form.selected_tool_ids.length === 0 ? (_jsx("span", { children: "None" })) : (_jsx("span", { children: form.selected_tool_ids
                                                        .map((id) => tools.find((t) => t.id === id)?.display_name ?? id)
                                                        .join(", ") }))] }), _jsxs("div", { children: [_jsx("span", { className: "text-muted-foreground", children: "Data Sources: " }), form.data_sources.length === 0 ? (_jsx("span", { children: "None" })) : (_jsx("span", { children: form.data_sources.map((ds) => `${ds.source_type}:${ds.source_identifier}`).join(", ") }))] }), _jsxs("div", { children: [_jsx("span", { className: "text-muted-foreground", children: "Output: " }), form.structured_output ? "Structured (JSON schema)" : "Free-form text"] })] }) }))] })] }), _jsxs("div", { className: "flex justify-between", children: [_jsx(Button, { variant: "ghost", onClick: goBack, disabled: currentStepIndex === 0, children: "Back" }), step === "review" ? (_jsx(Button, { onClick: handleSave, disabled: isSaving || !form.name || !form.model_id || !form.system_prompt, children: isSaving ? "Saving…" : isEdit ? "Save Changes" : "Create Agent" })) : (_jsx(Button, { onClick: goNext, disabled: (step === "identity" && !form.name) ||
                            (step === "model" && !form.model_id), children: "Next" }))] })] }));
}
