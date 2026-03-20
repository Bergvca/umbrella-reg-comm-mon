import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import type { RunStepOut } from "@/lib/types";

interface Props {
  steps: RunStepOut[];
}

const STEP_TYPE_VARIANT: Record<string, "default" | "secondary" | "outline"> = {
  llm: "default",
  tool: "secondary",
  tool_result: "outline",
};

export function RunStepInspector({ steps }: Props) {
  if (steps.length === 0) {
    return (
      <p className="text-sm text-muted-foreground py-2">No steps recorded.</p>
    );
  }

  return (
    <Accordion type="multiple" className="w-full">
      {steps.map((step) => (
        <AccordionItem key={step.id} value={step.id}>
          <AccordionTrigger className="text-sm hover:no-underline">
            <div className="flex items-center gap-3 text-left">
              <span className="text-muted-foreground tabular-nums w-6">
                {step.step_order + 1}.
              </span>
              <Badge variant={STEP_TYPE_VARIANT[step.step_type] ?? "outline"} className="text-xs">
                {step.step_type}
              </Badge>
              {step.tool_name && (
                <span className="font-mono text-xs text-muted-foreground">{step.tool_name}</span>
              )}
              {step.duration_ms != null && (
                <span className="ml-auto text-xs text-muted-foreground pr-2">
                  {step.duration_ms}ms
                </span>
              )}
            </div>
          </AccordionTrigger>
          <AccordionContent>
            <div className="space-y-3 pl-9 pb-2">
              <div>
                <p className="text-xs font-medium text-muted-foreground mb-1">Input</p>
                <pre className="text-xs bg-muted rounded p-2 overflow-auto max-h-40">
                  {JSON.stringify(step.input, null, 2)}
                </pre>
              </div>
              {step.output != null && (
                <div>
                  <p className="text-xs font-medium text-muted-foreground mb-1">Output</p>
                  <pre className="text-xs bg-muted rounded p-2 overflow-auto max-h-40">
                    {JSON.stringify(step.output, null, 2)}
                  </pre>
                </div>
              )}
              {step.token_usage != null && (
                <div>
                  <p className="text-xs font-medium text-muted-foreground mb-1">Tokens</p>
                  <pre className="text-xs bg-muted rounded p-2 overflow-auto">
                    {JSON.stringify(step.token_usage, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          </AccordionContent>
        </AccordionItem>
      ))}
    </Accordion>
  );
}
