import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ChevronDown, ChevronRight, Loader2, Check, AlertCircle } from "lucide-react";
import type { StreamStep } from "@/hooks/useAgentStream";

interface Props {
  steps: StreamStep[];
  isStreaming: boolean;
}

const TYPE_LABEL: Record<string, string> = {
  llm_call: "LLM",
  tool_call: "Tool",
  tool_result: "Result",
  tool_error: "Error",
};

const TYPE_VARIANT: Record<string, "default" | "secondary" | "outline" | "destructive"> = {
  llm_call: "default",
  tool_call: "secondary",
  tool_result: "outline",
  tool_error: "destructive",
};

function toolInputSummary(input: Record<string, unknown> | null): string {
  if (!input) return "";
  const ti = input.tool_input;
  if (typeof ti === "string") {
    return ti.length > 100 ? ti.slice(0, 100) + "\u2026" : ti;
  }
  const str = JSON.stringify(input);
  return str.length > 100 ? str.slice(0, 100) + "\u2026" : str;
}

export function LiveStepTrace({ steps, isStreaming }: Props) {
  const [expanded, setExpanded] = useState<Set<number>>(new Set());

  if (steps.length === 0 && isStreaming) {
    return (
      <div className="flex items-center gap-2 py-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        Starting agent...
      </div>
    );
  }

  if (steps.length === 0) return null;

  const toggle = (order: number) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(order)) next.delete(order);
      else next.add(order);
      return next;
    });
  };

  return (
    <div className="space-y-1">
      {steps.map((step) => {
        const isExpanded = expanded.has(step.stepOrder);
        const isRunning = step.status === "running";
        const isError = step.type === "tool_error";

        return (
          <div
            key={step.stepOrder}
            className="rounded border bg-background animate-in slide-in-from-top-1 duration-200"
          >
            <button
              className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-muted/50 transition-colors"
              onClick={() => toggle(step.stepOrder)}
            >
              {isRunning ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground shrink-0" />
              ) : isError ? (
                <AlertCircle className="h-3.5 w-3.5 text-destructive shrink-0" />
              ) : (
                <Check className="h-3.5 w-3.5 text-green-600 shrink-0" />
              )}

              <Badge
                variant={TYPE_VARIANT[step.type] ?? "outline"}
                className="text-xs shrink-0"
              >
                {TYPE_LABEL[step.type] ?? step.type}
              </Badge>

              {step.toolName && (
                <span className="font-mono text-xs text-muted-foreground">
                  {step.toolName}
                </span>
              )}

              {step.type === "llm_call" && isRunning && (
                <span className="text-xs text-muted-foreground">Thinking...</span>
              )}

              {step.type === "tool_call" && step.input && (
                <span className="text-xs text-muted-foreground truncate max-w-md">
                  {toolInputSummary(step.input)}
                </span>
              )}

              <span className="ml-auto flex items-center gap-2">
                {step.durationMs != null && (
                  <span className="text-xs text-muted-foreground tabular-nums">
                    {step.durationMs < 1000
                      ? `${step.durationMs}ms`
                      : `${(step.durationMs / 1000).toFixed(1)}s`}
                  </span>
                )}
                <Button variant="ghost" size="icon" className="h-5 w-5 shrink-0" tabIndex={-1}>
                  {isExpanded ? (
                    <ChevronDown className="h-3 w-3" />
                  ) : (
                    <ChevronRight className="h-3 w-3" />
                  )}
                </Button>
              </span>
            </button>

            {isExpanded && (
              <div className="border-t px-3 py-2 space-y-2">
                {step.input && (
                  <div>
                    <p className="text-xs font-medium text-muted-foreground mb-1">Input</p>
                    <pre className="text-xs bg-muted rounded p-2 overflow-auto max-h-40 whitespace-pre-wrap">
                      {JSON.stringify(step.input, null, 2)}
                    </pre>
                  </div>
                )}
                {step.output && (
                  <div>
                    <p className="text-xs font-medium text-muted-foreground mb-1">Output</p>
                    <pre className="text-xs bg-muted rounded p-2 overflow-auto max-h-40 whitespace-pre-wrap">
                      {JSON.stringify(step.output, null, 2)}
                    </pre>
                  </div>
                )}
                {step.tokenUsage && (
                  <div>
                    <p className="text-xs font-medium text-muted-foreground mb-1">Tokens</p>
                    <pre className="text-xs bg-muted rounded p-2 overflow-auto whitespace-pre-wrap">
                      {JSON.stringify(step.tokenUsage, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
