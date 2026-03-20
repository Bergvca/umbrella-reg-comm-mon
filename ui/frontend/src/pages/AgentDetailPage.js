import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useParams, useNavigate } from "react-router";
import { toast } from "sonner";
import { useAgent, useDeleteAgent, useCloneAgent } from "@/hooks/useAgents";
import { useAuthStore } from "@/stores/auth";
import { hasRole, formatRelative } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger, } from "@/components/ui/alert-dialog";
import { RunHistory } from "@/components/agents/RunHistory";
import { Copy, Pencil, Play, Trash2 } from "lucide-react";
export function AgentDetailPage() {
    const { id } = useParams();
    const navigate = useNavigate();
    const user = useAuthStore((s) => s.user);
    const isSupervisor = user ? hasRole(user.roles, "supervisor") : false;
    const isAdmin = user ? hasRole(user.roles, "admin") : false;
    const { data: agent, isLoading, isError } = useAgent(id);
    const deleteAgent = useDeleteAgent();
    const cloneAgent = useCloneAgent();
    if (isLoading) {
        return (_jsxs("div", { className: "p-6 space-y-4", children: [_jsx(Skeleton, { className: "h-8 w-64" }), _jsx(Skeleton, { className: "h-40 w-full" })] }));
    }
    if (isError || !agent) {
        return (_jsx("div", { className: "p-6", children: _jsx(Card, { children: _jsx(CardContent, { className: "pt-6 text-center text-muted-foreground", children: "Agent not found." }) }) }));
    }
    return (_jsxs("div", { className: "p-6 space-y-6 max-w-4xl", children: [_jsxs("div", { className: "flex items-start justify-between", children: [_jsxs("div", { className: "space-y-1", children: [_jsxs("div", { className: "flex items-center gap-2", children: [_jsx("h1", { className: "text-2xl font-semibold", children: agent.name }), _jsx(Badge, { variant: agent.is_active ? "default" : "outline", children: agent.is_active ? "active" : "inactive" }), agent.is_builtin && (_jsx(Badge, { variant: "secondary", children: "built-in" }))] }), agent.description && (_jsx("p", { className: "text-muted-foreground", children: agent.description })), _jsxs("p", { className: "text-xs text-muted-foreground", children: ["Created ", formatRelative(agent.created_at)] })] }), _jsxs("div", { className: "flex gap-2", children: [_jsxs(Button, { variant: "outline", size: "sm", onClick: () => void navigate(`/agents/${agent.id}/playground`), children: [_jsx(Play, { className: "h-4 w-4 mr-1.5" }), "Playground"] }), isSupervisor && (_jsxs(Button, { variant: "outline", size: "sm", onClick: () => {
                                    cloneAgent.mutate(agent.id, {
                                        onSuccess: (cloned) => {
                                            toast.success("Agent cloned");
                                            void navigate(`/agents/${cloned.id}`);
                                        },
                                        onError: () => toast.error("Failed to clone agent"),
                                    });
                                }, disabled: cloneAgent.isPending, children: [_jsx(Copy, { className: "h-4 w-4 mr-1.5" }), "Clone"] })), isSupervisor && !agent.is_builtin && (_jsxs(Button, { variant: "outline", size: "sm", onClick: () => void navigate(`/agents/${agent.id}/edit`), children: [_jsx(Pencil, { className: "h-4 w-4 mr-1.5" }), "Edit"] })), isAdmin && !agent.is_builtin && (_jsxs(AlertDialog, { children: [_jsx(AlertDialogTrigger, { asChild: true, children: _jsxs(Button, { variant: "destructive", size: "sm", children: [_jsx(Trash2, { className: "h-4 w-4 mr-1.5" }), "Delete"] }) }), _jsxs(AlertDialogContent, { children: [_jsxs(AlertDialogHeader, { children: [_jsx(AlertDialogTitle, { children: "Delete agent?" }), _jsxs(AlertDialogDescription, { children: ["This will deactivate ", _jsx("strong", { children: agent.name }), ". Run history will be preserved."] })] }), _jsxs(AlertDialogFooter, { children: [_jsx(AlertDialogCancel, { children: "Cancel" }), _jsx(AlertDialogAction, { onClick: () => deleteAgent.mutate(agent.id, {
                                                            onSuccess: () => {
                                                                toast.success("Agent deleted");
                                                                void navigate("/agents");
                                                            },
                                                            onError: () => toast.error("Failed to delete agent"),
                                                        }), children: "Delete" })] })] })] }))] })] }), _jsxs(Card, { children: [_jsx(CardHeader, { children: _jsx(CardTitle, { children: "Configuration" }) }), _jsxs(CardContent, { className: "space-y-4", children: [_jsxs("div", { className: "grid grid-cols-2 gap-4 text-sm", children: [_jsxs("div", { children: [_jsx("p", { className: "text-muted-foreground text-xs mb-1", children: "Model" }), _jsx("p", { className: "font-medium", children: agent.model.name }), _jsxs("p", { className: "text-xs text-muted-foreground", children: [agent.model.provider, " / ", agent.model.model_id] })] }), _jsxs("div", { children: [_jsx("p", { className: "text-muted-foreground text-xs mb-1", children: "Parameters" }), _jsxs("p", { children: ["Temperature: ", agent.temperature] }), _jsxs("p", { children: ["Max iterations: ", agent.max_iterations] })] })] }), _jsxs("div", { children: [_jsx("p", { className: "text-muted-foreground text-xs mb-1", children: "System Prompt" }), _jsx("pre", { className: "text-sm bg-muted rounded p-3 whitespace-pre-wrap font-mono max-h-40 overflow-auto", children: agent.system_prompt })] }), agent.output_schema && (_jsxs("div", { children: [_jsx("p", { className: "text-muted-foreground text-xs mb-1", children: "Output Schema" }), _jsx("pre", { className: "text-xs bg-muted rounded p-3 overflow-auto max-h-40", children: JSON.stringify(agent.output_schema, null, 2) })] }))] })] }), _jsxs(Card, { children: [_jsx(CardHeader, { children: _jsxs(CardTitle, { children: ["Tools (", agent.tools.length, ")"] }) }), _jsx(CardContent, { children: agent.tools.length === 0 ? (_jsx("p", { className: "text-sm text-muted-foreground", children: "No tools configured." })) : (_jsx("div", { className: "flex flex-wrap gap-2", children: agent.tools.map((t) => (_jsx(Badge, { variant: "secondary", children: t.display_name }, t.id))) })) })] }), _jsxs(Card, { children: [_jsx(CardHeader, { children: _jsxs(CardTitle, { children: ["Data Sources (", agent.data_sources.length, ")"] }) }), _jsx(CardContent, { children: agent.data_sources.length === 0 ? (_jsx("p", { className: "text-sm text-muted-foreground", children: "No data sources configured." })) : (_jsx("div", { className: "space-y-2", children: agent.data_sources.map((ds, i) => (_jsxs("div", { className: "flex items-center gap-2 text-sm", children: [_jsx(Badge, { variant: "outline", children: ds.source_type }), _jsx("span", { className: "font-mono text-xs", children: ds.source_identifier })] }, i))) })) })] }), _jsxs(Card, { children: [_jsx(CardHeader, { children: _jsx(CardTitle, { children: "Run History" }) }), _jsx(CardContent, { children: _jsx(RunHistory, { agentId: agent.id }) })] })] }));
}
