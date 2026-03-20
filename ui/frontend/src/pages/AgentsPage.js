import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useSearchParams, useNavigate } from "react-router";
import { AgentTable } from "@/components/agents/AgentTable";
import { useAgents } from "@/hooks/useAgents";
import { useAuthStore } from "@/stores/auth";
import { hasRole } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
const LIMIT = 50;
export function AgentsPage() {
    const [searchParams, setSearchParams] = useSearchParams();
    const navigate = useNavigate();
    const user = useAuthStore((s) => s.user);
    const isSupervisor = user ? hasRole(user.roles, "supervisor") : false;
    const tab = (searchParams.get("tab") ?? "all");
    const offset = Number(searchParams.get("offset") ?? 0);
    const queryParams = {
        ...(tab === "builtin" ? { is_builtin: true } : tab === "mine" ? { is_builtin: false } : {}),
        offset,
        limit: LIMIT,
    };
    const { data, isLoading, isError, refetch } = useAgents(queryParams);
    function handleTabChange(value) {
        setSearchParams({ tab: value });
    }
    function handlePageChange(newOffset) {
        const params = { tab };
        if (newOffset > 0)
            params.offset = String(newOffset);
        setSearchParams(params);
    }
    if (isError) {
        return (_jsx("div", { className: "p-6", children: _jsx(Card, { children: _jsxs(CardContent, { className: "pt-6 text-center space-y-3", children: [_jsx("p", { className: "text-muted-foreground", children: "Failed to load agents." }), _jsx(Button, { variant: "outline", onClick: () => void refetch(), children: "Retry" })] }) }) }));
    }
    return (_jsxs("div", { className: "p-6 space-y-4", children: [_jsxs("div", { className: "flex items-center justify-between", children: [_jsx("h1", { className: "text-2xl font-semibold", children: "Agents" }), isSupervisor && (_jsx(Button, { onClick: () => void navigate("/agents/new"), children: "New Agent" }))] }), _jsx(Tabs, { value: tab, onValueChange: handleTabChange, children: _jsxs(TabsList, { children: [_jsx(TabsTrigger, { value: "all", children: "All" }), _jsx(TabsTrigger, { value: "mine", children: "Custom" }), _jsx(TabsTrigger, { value: "builtin", children: "Built-in" })] }) }), _jsx(AgentTable, { data: data?.items, total: data?.total, offset: offset, limit: LIMIT, onPageChange: handlePageChange, isLoading: isLoading })] }));
}
