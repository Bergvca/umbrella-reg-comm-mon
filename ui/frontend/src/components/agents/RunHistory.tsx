import { useState } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { ChevronDown, ChevronRight, Loader2 } from "lucide-react";
import { useAgentRuns, useAgentRun } from "@/hooks/useAgents";
import { RunStepInspector } from "./RunStepInspector";
import { formatRelative } from "@/lib/utils";
import type { RunOut } from "@/lib/types";

interface Props {
  agentId: string;
}

const STATUS_VARIANT: Record<string, "default" | "secondary" | "outline" | "destructive"> = {
  completed: "default",
  running: "secondary",
  pending: "outline",
  failed: "destructive",
  cancelled: "outline",
};

function durationLabel(ms: number | null): string {
  if (ms == null) return "—";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function inputSnippet(input: Record<string, unknown>): string {
  const prompt = input.prompt ?? input.input ?? Object.values(input)[0] ?? "";
  const str = String(prompt);
  return str.length > 80 ? str.slice(0, 80) + "…" : str;
}

function outputSnippet(output: Record<string, unknown> | null): string {
  if (!output) return "";
  const response = output.response ?? output.output ?? Object.values(output)[0] ?? "";
  return String(response);
}

function totalTokens(usage: Record<string, unknown> | null): string {
  if (!usage) return "—";
  const total = usage.total_tokens ?? usage.total ?? null;
  return total != null ? String(total) : "—";
}

const PROSE_CLASSES =
  "prose prose-sm max-w-none prose-p:text-foreground prose-headings:text-foreground prose-strong:text-foreground prose-li:text-foreground prose-td:text-foreground prose-th:text-foreground prose-table:w-full prose-table:border-collapse prose-td:border prose-td:border-border prose-td:px-3 prose-td:py-1.5 prose-th:border prose-th:border-border prose-th:px-3 prose-th:py-1.5 prose-th:bg-muted prose-th:font-semibold";

function ExpandedRunDetail({ runId, run }: { runId: string; run: RunOut }) {
  const { data: fullRun, isLoading } = useAgentRun(runId);
  const detail = fullRun ?? run;
  const steps = detail.steps;

  return (
    <div className="space-y-3">
      {detail.output && (
        <div>
          <p className="text-xs font-medium text-muted-foreground mb-1">Output</p>
          <div className="bg-background rounded border p-3 max-h-96 overflow-auto">
            <div className={PROSE_CLASSES}>
              <Markdown remarkPlugins={[remarkGfm]}>
                {outputSnippet(detail.output)}
              </Markdown>
            </div>
          </div>
        </div>
      )}
      {detail.error_message && (
        <div>
          <p className="text-xs font-medium text-destructive mb-1">Error</p>
          <pre className="text-sm whitespace-pre-wrap bg-background rounded border border-destructive/30 p-3 max-h-40 overflow-auto text-destructive">
            {detail.error_message}
          </pre>
        </div>
      )}
      {isLoading ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground py-2">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading steps…
        </div>
      ) : steps && steps.length > 0 ? (
        <RunStepInspector steps={steps} />
      ) : (
        <p className="text-sm text-muted-foreground">No step details available.</p>
      )}
    </div>
  );
}

export function RunHistory({ agentId }: Props) {
  const { data, isLoading } = useAgentRuns({ agent_id: agentId, limit: 20 });
  const [expandedRunId, setExpandedRunId] = useState<string | null>(null);

  const headers = (
    <TableRow>
      <TableHead className="w-8" />
      <TableHead>Status</TableHead>
      <TableHead>Input</TableHead>
      <TableHead>Duration</TableHead>
      <TableHead>Tokens</TableHead>
      <TableHead>Started</TableHead>
    </TableRow>
  );

  if (isLoading) {
    return (
      <div className="rounded-md border">
        <Table>
          <TableHeader>{headers}</TableHeader>
          <TableBody>
            {Array.from({ length: 3 }).map((_, i) => (
              <TableRow key={i}>
                <TableCell><Skeleton className="h-4 w-4" /></TableCell>
                <TableCell><Skeleton className="h-5 w-20" /></TableCell>
                <TableCell><Skeleton className="h-5 w-48" /></TableCell>
                <TableCell><Skeleton className="h-5 w-16" /></TableCell>
                <TableCell><Skeleton className="h-5 w-12" /></TableCell>
                <TableCell><Skeleton className="h-5 w-24" /></TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    );
  }

  if (!data || data.items.length === 0) {
    return (
      <div className="rounded-md border">
        <Table>
          <TableHeader>{headers}</TableHeader>
          <TableBody>
            <TableRow>
              <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                No runs yet.
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </div>
    );
  }

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>{headers}</TableHeader>
        <TableBody>
          {data.items.map((run: RunOut) => (
            <>
              <TableRow
                key={run.id}
                className="cursor-pointer hover:bg-muted/50"
                onClick={() =>
                  setExpandedRunId((prev) => (prev === run.id ? null : run.id))
                }
              >
                <TableCell>
                  <Button variant="ghost" size="icon" className="h-6 w-6">
                    {expandedRunId === run.id ? (
                      <ChevronDown className="h-4 w-4" />
                    ) : (
                      <ChevronRight className="h-4 w-4" />
                    )}
                  </Button>
                </TableCell>
                <TableCell>
                  <Badge variant={STATUS_VARIANT[run.status] ?? "outline"}>
                    {run.status}
                  </Badge>
                </TableCell>
                <TableCell className="text-sm text-muted-foreground max-w-xs truncate">
                  {inputSnippet(run.input)}
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {durationLabel(run.duration_ms)}
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {totalTokens(run.token_usage)}
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {formatRelative(run.created_at)}
                </TableCell>
              </TableRow>
              {expandedRunId === run.id && (
                <TableRow key={`${run.id}-steps`}>
                  <TableCell colSpan={6} className="bg-muted/30 px-4 py-3 space-y-3">
                    <ExpandedRunDetail runId={run.id} run={run} />
                  </TableCell>
                </TableRow>
              )}
            </>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
