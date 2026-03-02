import { useEffect, useRef, useState } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { AlertCircle, Send, Square } from "lucide-react";
import { useAgentStream } from "@/hooks/useAgentStream";
import { LiveStepTrace } from "./LiveStepTrace";
import type { AgentOut } from "@/lib/types";
import type { PlaygroundRun } from "@/hooks/useAgentStream";

interface Props {
  agent: AgentOut;
}

const STATUS_VARIANT: Record<string, "default" | "secondary" | "outline" | "destructive"> = {
  completed: "default",
  running: "secondary",
  failed: "destructive",
  cancelled: "outline",
};

function RunCard({ run, isActive }: { run: PlaygroundRun; isActive: boolean }) {
  return (
    <Card className="mb-4">
      <CardContent className="pt-4 space-y-3">
        {/* Input */}
        <div className="flex items-start gap-2">
          <Badge variant="outline" className="shrink-0 mt-0.5">
            You
          </Badge>
          <p className="text-sm whitespace-pre-wrap">{run.input}</p>
        </div>

        {/* Steps */}
        <LiveStepTrace steps={run.steps} isStreaming={isActive} />

        {/* Error */}
        {run.status === "failed" && run.errorMessage && (
          <div className="flex items-start gap-2 rounded-md border border-destructive/50 bg-destructive/10 px-3 py-2 text-destructive">
            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
            <p className="text-sm whitespace-pre-wrap">{run.errorMessage}</p>
          </div>
        )}

        {/* Output */}
        {run.output && (
          <div className="flex items-start gap-2">
            <Badge
              variant={STATUS_VARIANT[run.status] ?? "outline"}
              className="shrink-0 mt-0.5"
            >
              Agent
            </Badge>
            <div className="text-sm prose prose-sm max-w-none prose-p:text-foreground prose-headings:text-foreground prose-strong:text-foreground prose-li:text-foreground prose-td:text-foreground prose-th:text-foreground prose-table:w-full prose-table:border-collapse prose-td:border prose-td:border-border prose-td:px-3 prose-td:py-1.5 prose-th:border prose-th:border-border prose-th:px-3 prose-th:py-1.5 prose-th:bg-muted prose-th:font-semibold">
              <Markdown remarkPlugins={[remarkGfm]}>{run.output}</Markdown>
            </div>
          </div>
        )}

        {/* Metadata */}
        {run.status !== "running" && (
          <div className="flex items-center gap-3 text-xs text-muted-foreground border-t pt-2">
            <Badge variant={STATUS_VARIANT[run.status] ?? "outline"} className="text-xs">
              {run.status}
            </Badge>
            {run.durationMs != null && (
              <span>
                {run.durationMs < 1000
                  ? `${run.durationMs}ms`
                  : `${(run.durationMs / 1000).toFixed(1)}s`}
              </span>
            )}
            {run.totalTokens != null && (
              <span>{run.totalTokens.toLocaleString()} tokens</span>
            )}
            {run.iterations != null && (
              <span>{run.iterations} steps</span>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export function AgentPlayground({ agent }: Props) {
  const { runs, isStreaming, startRun, cancelRun } =
    useAgentStream(agent.id);
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll when new content arrives
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [runs]);

  const handleSubmit = async () => {
    const trimmed = input.trim();
    if (!trimmed || isStreaming) return;
    setInput("");
    await startRun(trimmed);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void handleSubmit();
    }
  };

  // Session totals
  const sessionTokens = runs.reduce((sum, r) => sum + (r.totalTokens ?? 0), 0);

  return (
    <div className="flex flex-col h-[calc(100vh-12rem)]">
      {/* Scrollable run area */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-2">
        {runs.length === 0 && (
          <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
            Type a prompt below to test <strong className="mx-1">{agent.name}</strong>.
          </div>
        )}
        {runs.map((run, i) => (
          <RunCard
            key={run.runId}
            run={run}
            isActive={i === runs.length - 1 && run.status === "running"}
          />
        ))}
      </div>

      {/* Input area */}
      <div className="border-t p-4 space-y-2">
        <div className="flex gap-2">
          <textarea
            ref={textareaRef}
            className="flex-1 min-h-[2.5rem] max-h-32 rounded-md border bg-background px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-ring"
            placeholder={`Ask ${agent.name} something...`}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isStreaming}
            rows={1}
          />
          {isStreaming ? (
            <Button variant="destructive" size="icon" onClick={() => void cancelRun()}>
              <Square className="h-4 w-4" />
            </Button>
          ) : (
            <Button
              size="icon"
              onClick={() => void handleSubmit()}
              disabled={!input.trim()}
            >
              <Send className="h-4 w-4" />
            </Button>
          )}
        </div>

        {/* Footer metadata */}
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          <span>Model: {agent.model.name}</span>
          <span>Temperature: {agent.temperature}</span>
          <span>Max iterations: {agent.max_iterations}</span>
          {runs.length > 0 && (
            <span className="ml-auto">
              Session: {runs.length} run{runs.length !== 1 ? "s" : ""}
              {sessionTokens > 0 && `, ${sessionTokens.toLocaleString()} tokens`}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
