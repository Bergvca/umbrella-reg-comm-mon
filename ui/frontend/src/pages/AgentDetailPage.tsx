import { useParams, useNavigate } from "react-router";
import { toast } from "sonner";
import { useAgent, useDeleteAgent, useCloneAgent } from "@/hooks/useAgents";
import { useAuthStore } from "@/stores/auth";
import { hasRole, formatRelative } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { RunHistory } from "@/components/agents/RunHistory";
import { Copy, Pencil, Play, Trash2 } from "lucide-react";

export function AgentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const isSupervisor = user ? hasRole(user.roles, "supervisor") : false;
  const isAdmin = user ? hasRole(user.roles, "admin") : false;

  const { data: agent, isLoading, isError } = useAgent(id!);
  const deleteAgent = useDeleteAgent();
  const cloneAgent = useCloneAgent();

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-40 w-full" />
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
    <div className="p-6 space-y-6 max-w-4xl">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-semibold">{agent.name}</h1>
            <Badge variant={agent.is_active ? "default" : "outline"}>
              {agent.is_active ? "active" : "inactive"}
            </Badge>
            {agent.is_builtin && (
              <Badge variant="secondary">built-in</Badge>
            )}
          </div>
          {agent.description && (
            <p className="text-muted-foreground">{agent.description}</p>
          )}
          <p className="text-xs text-muted-foreground">
            Created {formatRelative(agent.created_at)}
          </p>
        </div>

        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => void navigate(`/agents/${agent.id}/playground`)}
          >
            <Play className="h-4 w-4 mr-1.5" />
            Playground
          </Button>
          {isSupervisor && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                cloneAgent.mutate(agent.id, {
                  onSuccess: (cloned) => {
                    toast.success("Agent cloned");
                    void navigate(`/agents/${cloned.id}`);
                  },
                  onError: () => toast.error("Failed to clone agent"),
                });
              }}
              disabled={cloneAgent.isPending}
            >
              <Copy className="h-4 w-4 mr-1.5" />
              Clone
            </Button>
          )}
          {isSupervisor && !agent.is_builtin && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => void navigate(`/agents/${agent.id}/edit`)}
            >
              <Pencil className="h-4 w-4 mr-1.5" />
              Edit
            </Button>
          )}
          {isAdmin && !agent.is_builtin && (
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button variant="destructive" size="sm">
                  <Trash2 className="h-4 w-4 mr-1.5" />
                  Delete
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Delete agent?</AlertDialogTitle>
                  <AlertDialogDescription>
                    This will deactivate <strong>{agent.name}</strong>. Run history will be preserved.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                  <AlertDialogAction
                    onClick={() =>
                      deleteAgent.mutate(agent.id, {
                        onSuccess: () => {
                          toast.success("Agent deleted");
                          void navigate("/agents");
                        },
                        onError: () => toast.error("Failed to delete agent"),
                      })
                    }
                  >
                    Delete
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          )}
        </div>
      </div>

      {/* Configuration */}
      <Card>
        <CardHeader>
          <CardTitle>Configuration</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <p className="text-muted-foreground text-xs mb-1">Model</p>
              <p className="font-medium">{agent.model.name}</p>
              <p className="text-xs text-muted-foreground">{agent.model.provider} / {agent.model.model_id}</p>
            </div>
            <div>
              <p className="text-muted-foreground text-xs mb-1">Parameters</p>
              <p>Temperature: {agent.temperature}</p>
              <p>Max iterations: {agent.max_iterations}</p>
            </div>
          </div>
          <div>
            <p className="text-muted-foreground text-xs mb-1">System Prompt</p>
            <pre className="text-sm bg-muted rounded p-3 whitespace-pre-wrap font-mono max-h-40 overflow-auto">
              {agent.system_prompt}
            </pre>
          </div>
          {agent.output_schema && (
            <div>
              <p className="text-muted-foreground text-xs mb-1">Output Schema</p>
              <pre className="text-xs bg-muted rounded p-3 overflow-auto max-h-40">
                {JSON.stringify(agent.output_schema, null, 2)}
              </pre>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Tools */}
      <Card>
        <CardHeader>
          <CardTitle>Tools ({agent.tools.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {agent.tools.length === 0 ? (
            <p className="text-sm text-muted-foreground">No tools configured.</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {agent.tools.map((t) => (
                <Badge key={t.id} variant="secondary">{t.display_name}</Badge>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Data Sources */}
      <Card>
        <CardHeader>
          <CardTitle>Data Sources ({agent.data_sources.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {agent.data_sources.length === 0 ? (
            <p className="text-sm text-muted-foreground">No data sources configured.</p>
          ) : (
            <div className="space-y-2">
              {agent.data_sources.map((ds, i) => (
                <div key={i} className="flex items-center gap-2 text-sm">
                  <Badge variant="outline">{ds.source_type}</Badge>
                  <span className="font-mono text-xs">{ds.source_identifier}</span>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Run History */}
      <Card>
        <CardHeader>
          <CardTitle>Run History</CardTitle>
        </CardHeader>
        <CardContent>
          <RunHistory agentId={agent.id} />
        </CardContent>
      </Card>
    </div>
  );
}
