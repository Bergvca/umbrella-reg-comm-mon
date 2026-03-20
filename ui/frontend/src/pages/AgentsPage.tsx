import { useSearchParams, useNavigate } from "react-router";
import { AgentTable } from "@/components/agents/AgentTable";
import { useAgents } from "@/hooks/useAgents";
import { useAuthStore } from "@/stores/auth";
import { hasRole } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

const LIMIT = 50;

type Tab = "all" | "mine" | "builtin";

export function AgentsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const isSupervisor = user ? hasRole(user.roles, "supervisor") : false;

  const tab = (searchParams.get("tab") ?? "all") as Tab;
  const offset = Number(searchParams.get("offset") ?? 0);

  const queryParams = {
    ...(tab === "builtin" ? { is_builtin: true } : tab === "mine" ? { is_builtin: false } : {}),
    offset,
    limit: LIMIT,
  };

  const { data, isLoading, isError, refetch } = useAgents(queryParams);

  function handleTabChange(value: string) {
    setSearchParams({ tab: value });
  }

  function handlePageChange(newOffset: number) {
    const params: Record<string, string> = { tab };
    if (newOffset > 0) params.offset = String(newOffset);
    setSearchParams(params);
  }

  if (isError) {
    return (
      <div className="p-6">
        <Card>
          <CardContent className="pt-6 text-center space-y-3">
            <p className="text-muted-foreground">Failed to load agents.</p>
            <Button variant="outline" onClick={() => void refetch()}>
              Retry
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Agents</h1>
        {isSupervisor && (
          <Button onClick={() => void navigate("/agents/new")}>New Agent</Button>
        )}
      </div>

      <Tabs value={tab} onValueChange={handleTabChange}>
        <TabsList>
          <TabsTrigger value="all">All</TabsTrigger>
          <TabsTrigger value="mine">Custom</TabsTrigger>
          <TabsTrigger value="builtin">Built-in</TabsTrigger>
        </TabsList>
      </Tabs>

      <AgentTable
        data={data?.items}
        total={data?.total}
        offset={offset}
        limit={LIMIT}
        onPageChange={handlePageChange}
        isLoading={isLoading}
      />
    </div>
  );
}
