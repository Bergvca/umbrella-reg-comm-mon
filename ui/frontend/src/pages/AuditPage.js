import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useSearchParams } from "react-router";
import { AuditFilterBar } from "@/components/audit/AuditFilterBar";
import { AuditLogTable } from "@/components/audit/AuditLogTable";
import { useAuditLog } from "@/hooks/useAuditLog";
export function AuditPage() {
    const [searchParams, setSearchParams] = useSearchParams();
    const params = {
        actor_id: searchParams.get("actor_id") ?? undefined,
        object_type: searchParams.get("object_type") ?? undefined,
        date_from: searchParams.get("date_from") ?? undefined,
        date_to: searchParams.get("date_to") ?? undefined,
        offset: Number(searchParams.get("offset") ?? 0),
        limit: 50,
    };
    const { data, isLoading } = useAuditLog(params);
    function updateParams(next) {
        const p = {};
        if (next.actor_id)
            p.actor_id = next.actor_id;
        if (next.object_type)
            p.object_type = next.object_type;
        if (next.date_from)
            p.date_from = next.date_from;
        if (next.date_to)
            p.date_to = next.date_to;
        setSearchParams(p);
    }
    return (_jsxs("div", { className: "p-6 space-y-6 max-w-5xl", children: [_jsx("h1", { className: "text-2xl font-semibold", children: "Audit Log" }), _jsx(AuditFilterBar, { params: params, onChange: updateParams }), _jsx(AuditLogTable, { entries: data?.items ?? [], isLoading: isLoading })] }));
}
