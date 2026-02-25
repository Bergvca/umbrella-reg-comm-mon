import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useNavigate } from "react-router";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow, } from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { MyQueueList } from "@/components/queues/MyQueueList";
import { CreateQueueDialog } from "@/components/queues/CreateQueueDialog";
import { useQueues } from "@/hooks/useQueues";
import { useAuthStore } from "@/stores/auth";
import { hasRole } from "@/lib/utils";
import { formatRelative } from "@/lib/utils";
export function QueuesPage() {
    const navigate = useNavigate();
    const user = useAuthStore((s) => s.user);
    const isSupervisor = user ? hasRole(user.roles, "supervisor") : false;
    const { data: queuesData, isLoading: loadingQueues } = useQueues();
    if (!isSupervisor) {
        return (_jsxs("div", { className: "p-6 space-y-4", children: [_jsx("h1", { className: "text-2xl font-semibold", children: "My Queue" }), _jsx(MyQueueList, {})] }));
    }
    return (_jsxs("div", { className: "p-6 space-y-4", children: [_jsxs("div", { className: "flex items-center justify-between", children: [_jsx("h1", { className: "text-2xl font-semibold", children: "Review Queues" }), _jsx(CreateQueueDialog, {})] }), _jsxs(Tabs, { defaultValue: "my-queue", children: [_jsxs(TabsList, { children: [_jsx(TabsTrigger, { value: "my-queue", children: "My Batches" }), _jsx(TabsTrigger, { value: "all-queues", children: "All Queues" })] }), _jsx(TabsContent, { value: "my-queue", className: "mt-4", children: _jsx(MyQueueList, {}) }), _jsx(TabsContent, { value: "all-queues", className: "mt-4", children: loadingQueues ? (_jsx("div", { className: "space-y-2", children: Array.from({ length: 4 }).map((_, i) => (_jsx(Skeleton, { className: "h-10 w-full" }, i))) })) : (_jsx("div", { className: "rounded-md border", children: _jsxs(Table, { children: [_jsx(TableHeader, { children: _jsxs(TableRow, { children: [_jsx(TableHead, { children: "Name" }), _jsx(TableHead, { children: "Batches" }), _jsx(TableHead, { children: "Total Items" }), _jsx(TableHead, { children: "Created" })] }) }), _jsx(TableBody, { children: !queuesData?.items?.length ? (_jsx(TableRow, { children: _jsx(TableCell, { colSpan: 4, className: "text-center py-8 text-muted-foreground", children: "No queues found." }) })) : (queuesData.items.map((q) => (_jsxs(TableRow, { className: "cursor-pointer hover:bg-muted/50", onClick: () => void navigate(`/queues/${q.id}`), children: [_jsx(TableCell, { className: "font-medium", children: q.name }), _jsx(TableCell, { className: "text-muted-foreground", children: "\u2014" }), _jsx(TableCell, { className: "text-muted-foreground", children: "\u2014" }), _jsx(TableCell, { className: "text-muted-foreground text-sm", children: formatRelative(q.created_at) })] }, q.id)))) })] }) })) })] })] }));
}
