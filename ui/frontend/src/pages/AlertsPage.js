import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useSearchParams } from "react-router";
import { AlertFilters } from "@/components/alerts/AlertFilters";
import { AlertTable } from "@/components/alerts/AlertTable";
import { useAlerts } from "@/hooks/useAlerts";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
const LIMIT = 50;
export function AlertsPage() {
    const [searchParams, setSearchParams] = useSearchParams();
    const severity = searchParams.get("severity") ?? undefined;
    const status = searchParams.get("status") ?? undefined;
    const offset = Number(searchParams.get("offset") ?? 0);
    const filters = { severity, status };
    const { data, isLoading, isError, refetch } = useAlerts({
        severity,
        status,
        offset,
        limit: LIMIT,
    });
    function handleFiltersChange(next) {
        const params = {};
        if (next.severity)
            params.severity = next.severity;
        if (next.status)
            params.status = next.status;
        // reset pagination on filter change
        setSearchParams(params);
    }
    function handlePageChange(newOffset) {
        const params = {};
        if (severity)
            params.severity = severity;
        if (status)
            params.status = status;
        if (newOffset > 0)
            params.offset = String(newOffset);
        setSearchParams(params);
    }
    if (isError) {
        return (_jsx("div", { className: "p-6", children: _jsx(Card, { children: _jsxs(CardContent, { className: "pt-6 text-center space-y-3", children: [_jsx("p", { className: "text-muted-foreground", children: "Failed to load alerts." }), _jsx(Button, { variant: "outline", onClick: () => void refetch(), children: "Retry" })] }) }) }));
    }
    return (_jsxs("div", { className: "p-6 space-y-4", children: [_jsx("h1", { className: "text-2xl font-semibold", children: "Alerts" }), _jsx(AlertFilters, { filters: filters, onChange: handleFiltersChange }), _jsx(AlertTable, { data: data?.items, total: data?.total, offset: offset, limit: LIMIT, onPageChange: handlePageChange, isLoading: isLoading })] }));
}
