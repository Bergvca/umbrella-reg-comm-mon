import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useParams, useNavigate } from "react-router";
import { useAgent } from "@/hooks/useAgents";
import { AgentPlayground } from "@/components/agents/AgentPlayground";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent } from "@/components/ui/card";
import { ArrowLeft, Settings, History } from "lucide-react";
export function AgentPlaygroundPage() {
    const { id } = useParams();
    const navigate = useNavigate();
    const { data: agent, isLoading, isError } = useAgent(id);
    if (isLoading) {
        return (_jsxs("div", { className: "p-6 space-y-4", children: [_jsx(Skeleton, { className: "h-8 w-64" }), _jsx(Skeleton, { className: "h-96 w-full" })] }));
    }
    if (isError || !agent) {
        return (_jsx("div", { className: "p-6", children: _jsx(Card, { children: _jsx(CardContent, { className: "pt-6 text-center text-muted-foreground", children: "Agent not found." }) }) }));
    }
    return (_jsxs("div", { className: "flex flex-col h-full", children: [_jsxs("div", { className: "border-b px-6 py-3 flex items-center justify-between shrink-0", children: [_jsxs("div", { className: "flex items-center gap-3", children: [_jsx(Button, { variant: "ghost", size: "icon", onClick: () => void navigate(`/agents/${id}`), children: _jsx(ArrowLeft, { className: "h-4 w-4" }) }), _jsxs("div", { children: [_jsxs("div", { className: "flex items-center gap-2", children: [_jsx("h1", { className: "text-lg font-semibold", children: agent.name }), _jsx(Badge, { variant: "secondary", className: "text-xs", children: "Playground" })] }), agent.description && (_jsx("p", { className: "text-xs text-muted-foreground", children: agent.description }))] })] }), _jsxs("div", { className: "flex items-center gap-2", children: [_jsxs(Button, { variant: "outline", size: "sm", onClick: () => void navigate(`/agents/${id}`), children: [_jsx(Settings, { className: "h-4 w-4 mr-1.5" }), "Config"] }), _jsxs(Button, { variant: "outline", size: "sm", onClick: () => void navigate(`/agents/${id}`), children: [_jsx(History, { className: "h-4 w-4 mr-1.5" }), "History"] })] })] }), _jsx("div", { className: "flex-1 min-h-0", children: _jsx(AgentPlayground, { agent: agent }) })] }));
}
