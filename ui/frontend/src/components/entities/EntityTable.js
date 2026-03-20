import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useNavigate } from "react-router";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow, } from "@/components/ui/table";
import { Pagination, PaginationContent, PaginationItem, PaginationNext, PaginationPrevious, } from "@/components/ui/pagination";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { formatRelative } from "@/lib/utils";
const TYPE_VARIANT = {
    person: "default",
    organization: "secondary",
    distribution_list: "outline",
};
export function EntityTable({ data, total = 0, offset, limit, onPageChange, isLoading }) {
    const navigate = useNavigate();
    const currentPage = Math.floor(offset / limit) + 1;
    const totalPages = Math.max(1, Math.ceil(total / limit));
    const headers = (_jsxs(TableRow, { children: [_jsx(TableHead, { children: "Name" }), _jsx(TableHead, { children: "Type" }), _jsx(TableHead, { children: "Handles" }), _jsx(TableHead, { children: "Created" })] }));
    if (isLoading) {
        return (_jsx("div", { className: "rounded-md border", children: _jsxs(Table, { children: [_jsx(TableHeader, { children: headers }), _jsx(TableBody, { children: Array.from({ length: 6 }).map((_, i) => (_jsxs(TableRow, { children: [_jsx(TableCell, { children: _jsx(Skeleton, { className: "h-5 w-40" }) }), _jsx(TableCell, { children: _jsx(Skeleton, { className: "h-5 w-24" }) }), _jsx(TableCell, { children: _jsx(Skeleton, { className: "h-5 w-32" }) }), _jsx(TableCell, { children: _jsx(Skeleton, { className: "h-5 w-24" }) })] }, i))) })] }) }));
    }
    if (!data || data.length === 0) {
        return (_jsx("div", { className: "rounded-md border", children: _jsxs(Table, { children: [_jsx(TableHeader, { children: headers }), _jsx(TableBody, { children: _jsx(TableRow, { children: _jsx(TableCell, { colSpan: 4, className: "text-center py-8 text-muted-foreground", children: "No entities found." }) }) })] }) }));
    }
    return (_jsxs("div", { className: "space-y-4", children: [_jsx("div", { className: "rounded-md border", children: _jsxs(Table, { children: [_jsx(TableHeader, { children: headers }), _jsx(TableBody, { children: data.map((entity) => (_jsxs(TableRow, { className: "cursor-pointer hover:bg-muted/50", onClick: () => void navigate(`/entities/${entity.id}`), children: [_jsx(TableCell, { className: "font-medium", children: entity.display_name }), _jsx(TableCell, { children: _jsx(Badge, { variant: TYPE_VARIANT[entity.entity_type] ?? "outline", children: entity.entity_type }) }), _jsx(TableCell, { className: "text-muted-foreground text-sm", children: entity.handles.length > 0
                                            ? entity.handles.map((h) => h.handle_value).join(", ")
                                            : "—" }), _jsx(TableCell, { className: "text-muted-foreground text-sm", children: formatRelative(entity.created_at) })] }, entity.id))) })] }) }), _jsxs("div", { className: "flex items-center justify-between text-sm text-muted-foreground", children: [_jsxs("span", { children: ["Showing ", offset + 1, "\u2013", Math.min(offset + limit, total), " of ", total] }), _jsx(Pagination, { children: _jsxs(PaginationContent, { children: [_jsx(PaginationItem, { children: _jsx(PaginationPrevious, { onClick: () => onPageChange(Math.max(0, offset - limit)), "aria-disabled": currentPage <= 1, className: currentPage <= 1 ? "pointer-events-none opacity-50" : "cursor-pointer" }) }), _jsx(PaginationItem, { children: _jsxs("span", { className: "px-3 py-1", children: ["Page ", currentPage, " of ", totalPages] }) }), _jsx(PaginationItem, { children: _jsx(PaginationNext, { onClick: () => onPageChange(offset + limit), "aria-disabled": currentPage >= totalPages, className: currentPage >= totalPages ? "pointer-events-none opacity-50" : "cursor-pointer" }) })] }) })] })] }));
}
