import { useParams, useNavigate } from "react-router";
import { useAgent } from "@/hooks/useAgents";
import { AgentPlayground } from "@/components/agents/AgentPlayground";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent } from "@/components/ui/card";
import { ArrowLeft, Settings, History } from "lucide-react";

export function AgentPlaygroundPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: agent, isLoading, isError } = useAgent(id!);

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }

  if (isError || !agent) {
    return (
      <div className="p-6">
        <Card>
          <CardContent className="pt-6 text-center text-muted-foreground">
            Agent not found.
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="border-b px-6 py-3 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => void navigate(`/agents/${id}`)}
          >
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-semibold">{agent.name}</h1>
              <Badge variant="secondary" className="text-xs">
                Playground
              </Badge>
            </div>
            {agent.description && (
              <p className="text-xs text-muted-foreground">{agent.description}</p>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => void navigate(`/agents/${id}`)}
          >
            <Settings className="h-4 w-4 mr-1.5" />
            Config
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => void navigate(`/agents/${id}`)}
          >
            <History className="h-4 w-4 mr-1.5" />
            History
          </Button>
        </div>
      </div>

      {/* Playground */}
      <div className="flex-1 min-h-0">
        <AgentPlayground agent={agent} />
      </div>
    </div>
  );
}
