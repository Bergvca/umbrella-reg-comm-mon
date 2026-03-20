import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router";
import { toast } from "sonner";
import { useAgent, useAgentModels, useAgentTools, useDataSourceOptions, useCreateAgent, useUpdateAgent } from "@/hooks/useAgents";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Plus, X } from "lucide-react";

type Step = "identity" | "model" | "instructions" | "tools" | "schema" | "review";

const STEPS: Step[] = ["identity", "model", "instructions", "tools", "schema", "review"];
const STEP_LABELS: Record<Step, string> = {
  identity: "Identity",
  model: "Model & Behavior",
  instructions: "Instructions",
  tools: "Tools & Data Sources",
  schema: "Output Schema",
  review: "Review & Save",
};

interface DataSource {
  source_type: "elasticsearch" | "postgresql";
  source_identifier: string;
}

interface FormState {
  name: string;
  description: string;
  model_id: string;
  temperature: number;
  max_iterations: number;
  system_prompt: string;
  selected_tool_ids: string[];
  data_sources: DataSource[];
  structured_output: boolean;
  output_schema_text: string;
}

const DEFAULT_FORM: FormState = {
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

function validateOutputSchema(text: string): Record<string, unknown> | null {
  if (!text.trim()) return null;
  try {
    return JSON.parse(text) as Record<string, unknown>;
  } catch {
    return undefined as unknown as Record<string, unknown> | null;
  }
}

export function AgentEditorPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const isEdit = !!id;

  const { data: existing, isLoading: loadingExisting } = useAgent(id ?? "");
  const { data: modelsData, isLoading: loadingModels } = useAgentModels();
  const { data: toolsData } = useAgentTools();
  const { data: dsOptions } = useDataSourceOptions();
  const createAgent = useCreateAgent();
  const updateAgent = useUpdateAgent();

  const [step, setStep] = useState<Step>("identity");
  const [form, setForm] = useState<FormState>(DEFAULT_FORM);
  const [schemaError, setSchemaError] = useState<string | null>(null);
  const [newDsType, setNewDsType] = useState<"elasticsearch" | "postgresql">("elasticsearch");
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

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function toggleTool(toolId: string) {
    setForm((prev) => ({
      ...prev,
      selected_tool_ids: prev.selected_tool_ids.includes(toolId)
        ? prev.selected_tool_ids.filter((id) => id !== toolId)
        : [...prev.selected_tool_ids, toolId],
    }));
  }

  function addDataSource() {
    if (!newDsId.trim()) return;
    setForm((prev) => ({
      ...prev,
      data_sources: [
        ...prev.data_sources,
        { source_type: newDsType, source_identifier: newDsId.trim() },
      ],
    }));
    setNewDsId("");
  }

  function removeDataSource(index: number) {
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
    let output_schema: Record<string, unknown> | null = null;
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
      updateAgent.mutate(
        { id: id!, body: payload },
        {
          onSuccess: (agent) => {
            toast.success("Agent updated");
            void navigate(`/agents/${agent.id}`);
          },
          onError: () => toast.error("Failed to update agent"),
        },
      );
    } else {
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
    return (
      <div className="p-6 space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const isSaving = createAgent.isPending || updateAgent.isPending;
  const models = modelsData?.items ?? [];
  const tools = toolsData?.items ?? [];

  return (
    <div className="p-6 max-w-2xl space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold">
          {isEdit ? "Edit Agent" : "New Agent"}
        </h1>
        {/* Step indicator */}
        <div className="flex items-center gap-1 text-sm">
          {STEPS.map((s, i) => (
            <span key={s} className="flex items-center gap-1">
              {i > 0 && <span className="text-muted-foreground">/</span>}
              <span
                className={s === step ? "font-medium text-foreground" : "text-muted-foreground"}
              >
                {STEP_LABELS[s]}
              </span>
            </span>
          ))}
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{STEP_LABELS[step]}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* ── Step 1: Identity ── */}
          {step === "identity" && (
            <>
              <div className="space-y-1">
                <Label>Name <span className="text-destructive">*</span></Label>
                <Input
                  value={form.name}
                  onChange={(e) => update("name", e.target.value)}
                  placeholder="e.g. Trade Surveillance Agent"
                />
              </div>
              <div className="space-y-1">
                <Label>Description</Label>
                <Input
                  value={form.description}
                  onChange={(e) => update("description", e.target.value)}
                  placeholder="Optional description"
                />
              </div>
            </>
          )}

          {/* ── Step 2: Model & Behavior ── */}
          {step === "model" && (
            <>
              <div className="space-y-1">
                <Label>Model <span className="text-destructive">*</span></Label>
                {loadingModels ? (
                  <Skeleton className="h-10 w-full" />
                ) : (
                  <Select value={form.model_id} onValueChange={(v) => update("model_id", v)}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select a model" />
                    </SelectTrigger>
                    <SelectContent>
                      {models.map((m) => (
                        <SelectItem key={m.id} value={m.id}>
                          {m.name} ({m.provider})
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              </div>
              <div className="space-y-1">
                <Label>Temperature ({form.temperature.toFixed(1)})</Label>
                <input
                  type="range"
                  min={0}
                  max={1}
                  step={0.1}
                  value={form.temperature}
                  onChange={(e) => update("temperature", Number(e.target.value))}
                  className="w-full"
                />
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>0.0 (precise)</span>
                  <span>1.0 (creative)</span>
                </div>
              </div>
              <div className="space-y-1">
                <Label>Max Iterations</Label>
                <Input
                  type="number"
                  min={1}
                  max={50}
                  value={form.max_iterations}
                  onChange={(e) => update("max_iterations", Number(e.target.value))}
                />
              </div>
            </>
          )}

          {/* ── Step 3: Instructions ── */}
          {step === "instructions" && (
            <div className="space-y-1">
              <Label>System Prompt <span className="text-destructive">*</span></Label>
              <Textarea
                rows={10}
                value={form.system_prompt}
                onChange={(e) => update("system_prompt", e.target.value)}
                placeholder="You are an AI assistant specialized in..."
                className="font-mono text-sm"
              />
            </div>
          )}

          {/* ── Step 4: Tools & Data Sources ── */}
          {step === "tools" && (
            <>
              <div className="space-y-2">
                <Label>Tools</Label>
                {tools.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No tools available.</p>
                ) : (
                  <div className="border rounded-md max-h-48 overflow-y-auto p-2 space-y-1">
                    {tools.map((tool) => (
                      <label
                        key={tool.id}
                        className="flex items-start gap-2 cursor-pointer p-1.5 hover:bg-muted rounded"
                      >
                        <input
                          type="checkbox"
                          className="mt-0.5"
                          checked={form.selected_tool_ids.includes(tool.id)}
                          onChange={() => toggleTool(tool.id)}
                        />
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium">{tool.display_name}</p>
                          <p className="text-xs text-muted-foreground truncate">
                            {tool.description}
                          </p>
                        </div>
                        <Badge variant="outline" className="text-xs shrink-0">
                          {tool.category}
                        </Badge>
                      </label>
                    ))}
                  </div>
                )}
              </div>

              <div className="space-y-2">
                <Label>Data Sources</Label>
                {form.data_sources.length > 0 && (
                  <div className="space-y-2">
                    {form.data_sources.map((ds, i) => (
                      <div key={i} className="flex items-center gap-2 text-sm">
                        <Badge variant="outline">{ds.source_type}</Badge>
                        <span className="font-mono text-xs flex-1">{ds.source_identifier}</span>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-6 w-6"
                          onClick={() => removeDataSource(i)}
                        >
                          <X className="h-3 w-3" />
                        </Button>
                      </div>
                    ))}
                  </div>
                )}
                <div className="flex gap-2">
                  <Select
                    value={newDsType}
                    onValueChange={(v) => {
                      setNewDsType(v as "elasticsearch" | "postgresql");
                      setNewDsId("");
                    }}
                  >
                    <SelectTrigger className="w-40">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="elasticsearch">Elasticsearch</SelectItem>
                      <SelectItem value="postgresql">PostgreSQL</SelectItem>
                    </SelectContent>
                  </Select>
                  {newDsType === "postgresql" ? (
                    <Select value={newDsId} onValueChange={(v) => setNewDsId(v)}>
                      <SelectTrigger className="flex-1">
                        <SelectValue placeholder="Select a table" />
                      </SelectTrigger>
                      <SelectContent>
                        {(dsOptions?.postgresql_tables ?? []).map((t) => (
                          <SelectItem key={t} value={t}>{t}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  ) : (
                    <>
                      <Input
                        list="es-index-options"
                        value={newDsId}
                        onChange={(e) => setNewDsId(e.target.value)}
                        placeholder="Index name or pattern (e.g. messages-*)"
                        className="flex-1"
                        onKeyDown={(e) => {
                          if (e.key === "Enter") { e.preventDefault(); addDataSource(); }
                        }}
                      />
                      <datalist id="es-index-options">
                        {(dsOptions?.elasticsearch_indices ?? []).map((idx) => (
                          <option key={idx} value={idx} />
                        ))}
                      </datalist>
                    </>
                  )}
                  <Button variant="outline" size="icon" onClick={addDataSource}>
                    <Plus className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </>
          )}

          {/* ── Step 5: Output Schema ── */}
          {step === "schema" && (
            <>
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="structured-output"
                  checked={form.structured_output}
                  onChange={(e) => update("structured_output", e.target.checked)}
                />
                <Label htmlFor="structured-output">Enable structured output</Label>
              </div>
              {form.structured_output && (
                <div className="space-y-1">
                  <Label>JSON Schema</Label>
                  <Textarea
                    rows={8}
                    value={form.output_schema_text}
                    onChange={(e) => {
                      update("output_schema_text", e.target.value);
                      setSchemaError(null);
                    }}
                    placeholder='{"type": "object", "properties": {...}}'
                    className="font-mono text-sm"
                  />
                  {schemaError && (
                    <p className="text-xs text-destructive">{schemaError}</p>
                  )}
                </div>
              )}
              {!form.structured_output && (
                <p className="text-sm text-muted-foreground">
                  The agent will return free-form text output.
                </p>
              )}
            </>
          )}

          {/* ── Step 6: Review ── */}
          {step === "review" && (
            <div className="space-y-4 text-sm">
              <div className="rounded-md border p-3 space-y-3">
                <div>
                  <span className="text-muted-foreground">Name: </span>
                  <span className="font-medium">{form.name || "—"}</span>
                  {form.description && (
                    <p className="text-muted-foreground text-xs mt-0.5">{form.description}</p>
                  )}
                </div>
                <div>
                  <span className="text-muted-foreground">Model: </span>
                  <span>{models.find((m) => m.id === form.model_id)?.name ?? "—"}</span>
                  <span className="text-muted-foreground ml-2">
                    (temp {form.temperature.toFixed(1)}, {form.max_iterations} iterations)
                  </span>
                </div>
                <div>
                  <p className="text-muted-foreground mb-1">System Prompt:</p>
                  <pre className="bg-muted rounded p-2 text-xs whitespace-pre-wrap max-h-24 overflow-auto">
                    {form.system_prompt || "—"}
                  </pre>
                </div>
                <div>
                  <span className="text-muted-foreground">Tools: </span>
                  {form.selected_tool_ids.length === 0 ? (
                    <span>None</span>
                  ) : (
                    <span>
                      {form.selected_tool_ids
                        .map((id) => tools.find((t) => t.id === id)?.display_name ?? id)
                        .join(", ")}
                    </span>
                  )}
                </div>
                <div>
                  <span className="text-muted-foreground">Data Sources: </span>
                  {form.data_sources.length === 0 ? (
                    <span>None</span>
                  ) : (
                    <span>
                      {form.data_sources.map((ds) => `${ds.source_type}:${ds.source_identifier}`).join(", ")}
                    </span>
                  )}
                </div>
                <div>
                  <span className="text-muted-foreground">Output: </span>
                  {form.structured_output ? "Structured (JSON schema)" : "Free-form text"}
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Navigation */}
      <div className="flex justify-between">
        <Button variant="ghost" onClick={goBack} disabled={currentStepIndex === 0}>
          Back
        </Button>
        {step === "review" ? (
          <Button
            onClick={handleSave}
            disabled={isSaving || !form.name || !form.model_id || !form.system_prompt}
          >
            {isSaving ? "Saving…" : isEdit ? "Save Changes" : "Create Agent"}
          </Button>
        ) : (
          <Button
            onClick={goNext}
            disabled={
              (step === "identity" && !form.name) ||
              (step === "model" && !form.model_id)
            }
          >
            Next
          </Button>
        )}
      </div>
    </div>
  );
}
