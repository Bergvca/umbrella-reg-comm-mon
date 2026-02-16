import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useSearchParams } from "react-router";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue, } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { SEVERITY_LEVELS, ALERT_STATUSES } from "@/lib/constants";
export function AlertFilters({ filters, onChange }) {
    const [, setSearchParams] = useSearchParams();
    function update(patch) {
        const next = { ...filters, ...patch };
        // remove undefined/empty values
        const params = {};
        if (next.severity)
            params.severity = next.severity;
        if (next.status)
            params.status = next.status;
        setSearchParams(params);
        onChange(next);
    }
    function clear() {
        setSearchParams({});
        onChange({});
    }
    return (_jsxs("div", { className: "flex flex-wrap items-center gap-3", children: [_jsxs("div", { className: "flex items-center gap-2", children: [_jsx("span", { className: "text-sm font-medium text-muted-foreground", children: "Severity:" }), _jsxs(Select, { value: filters.severity ?? "all", onValueChange: (v) => update({ severity: v === "all" ? undefined : v }), children: [_jsx(SelectTrigger, { className: "w-32", children: _jsx(SelectValue, {}) }), _jsxs(SelectContent, { children: [_jsx(SelectItem, { value: "all", children: "All" }), SEVERITY_LEVELS.map((s) => (_jsx(SelectItem, { value: s, children: s.charAt(0).toUpperCase() + s.slice(1) }, s)))] })] })] }), _jsxs("div", { className: "flex items-center gap-2", children: [_jsx("span", { className: "text-sm font-medium text-muted-foreground", children: "Status:" }), _jsxs(Select, { value: filters.status ?? "all", onValueChange: (v) => update({ status: v === "all" ? undefined : v }), children: [_jsx(SelectTrigger, { className: "w-36", children: _jsx(SelectValue, {}) }), _jsxs(SelectContent, { children: [_jsx(SelectItem, { value: "all", children: "All" }), ALERT_STATUSES.map((s) => (_jsx(SelectItem, { value: s, children: s === "in_review" ? "In Review" : s.charAt(0).toUpperCase() + s.slice(1) }, s)))] })] })] }), (filters.severity ?? filters.status) && (_jsx(Button, { variant: "ghost", size: "sm", onClick: clear, children: "Clear filters" }))] }));
}
