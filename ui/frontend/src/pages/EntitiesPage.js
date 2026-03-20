import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from "react";
import { useSearchParams } from "react-router";
import { toast } from "sonner";
import { EntityTable } from "@/components/entities/EntityTable";
import { EntityForm } from "@/components/entities/EntityForm";
import { BatchUploadDialog } from "@/components/entities/BatchUploadDialog";
import { useEntities, useCreateEntity, useBatchUploadCsv } from "@/hooks/useEntities";
import { useAuthStore } from "@/stores/auth";
import { hasRole } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue, } from "@/components/ui/select";
import { Card, CardContent } from "@/components/ui/card";
const LIMIT = 50;
export function EntitiesPage() {
    const [searchParams, setSearchParams] = useSearchParams();
    const user = useAuthStore((s) => s.user);
    const isAdmin = user ? hasRole(user.roles, "admin") : false;
    const entityType = searchParams.get("entity_type") ?? undefined;
    const search = searchParams.get("search") ?? undefined;
    const attrKey = searchParams.get("attr_key") ?? undefined;
    const attrValue = searchParams.get("attr_value") ?? undefined;
    const offset = Number(searchParams.get("offset") ?? 0);
    const { data, isLoading, isError, refetch } = useEntities({
        entity_type: entityType,
        search,
        attr_key: attrKey,
        attr_value: attrValue,
        offset,
        limit: LIMIT,
    });
    const [createOpen, setCreateOpen] = useState(false);
    const [batchOpen, setBatchOpen] = useState(false);
    const [batchResult, setBatchResult] = useState(null);
    const [searchInput, setSearchInput] = useState(search ?? "");
    const [attrKeyInput, setAttrKeyInput] = useState(attrKey ?? "");
    const [attrValueInput, setAttrValueInput] = useState(attrValue ?? "");
    const createEntity = useCreateEntity();
    const batchUpload = useBatchUploadCsv();
    function buildParams(overrides = {}) {
        const merged = { entity_type: entityType, search, attr_key: attrKey, attr_value: attrValue, ...overrides };
        const params = {};
        for (const [k, v] of Object.entries(merged)) {
            if (v && v !== "all")
                params[k] = v;
        }
        return params;
    }
    function handleFilterChange(type) {
        setSearchParams(buildParams({ entity_type: type === "all" ? undefined : type, offset: undefined }));
    }
    function handleSearch(e) {
        e.preventDefault();
        setSearchParams(buildParams({
            search: searchInput.trim() || undefined,
            attr_key: attrKeyInput.trim() || undefined,
            attr_value: attrValueInput.trim() || undefined,
            offset: undefined,
        }));
    }
    function handlePageChange(newOffset) {
        setSearchParams(buildParams({ offset: newOffset > 0 ? String(newOffset) : undefined }));
    }
    if (isError) {
        return (_jsx("div", { className: "p-6", children: _jsx(Card, { children: _jsxs(CardContent, { className: "pt-6 text-center space-y-3", children: [_jsx("p", { className: "text-muted-foreground", children: "Failed to load entities." }), _jsx(Button, { variant: "outline", onClick: () => void refetch(), children: "Retry" })] }) }) }));
    }
    return (_jsxs("div", { className: "p-6 space-y-4", children: [_jsxs("div", { className: "flex items-center justify-between", children: [_jsx("h1", { className: "text-2xl font-semibold", children: "Entities" }), isAdmin && (_jsxs("div", { className: "flex gap-2", children: [_jsx(Button, { variant: "outline", onClick: () => { setBatchResult(null); setBatchOpen(true); }, children: "Batch Upload" }), _jsx(Button, { onClick: () => setCreateOpen(true), children: "Create Entity" })] }))] }), _jsxs("div", { className: "flex gap-3 items-end", children: [_jsxs(Select, { value: entityType ?? "all", onValueChange: handleFilterChange, children: [_jsx(SelectTrigger, { className: "w-48", children: _jsx(SelectValue, { placeholder: "All types" }) }), _jsxs(SelectContent, { children: [_jsx(SelectItem, { value: "all", children: "All types" }), _jsx(SelectItem, { value: "person", children: "Person" }), _jsx(SelectItem, { value: "organization", children: "Organization" }), _jsx(SelectItem, { value: "distribution_list", children: "Distribution List" })] })] }), _jsxs("form", { onSubmit: handleSearch, className: "flex gap-2 items-end", children: [_jsx(Input, { placeholder: "Search by name...", value: searchInput, onChange: (e) => setSearchInput(e.target.value), className: "w-48" }), _jsx(Input, { placeholder: "Attr key", value: attrKeyInput, onChange: (e) => setAttrKeyInput(e.target.value), className: "w-32" }), _jsx(Input, { placeholder: "Attr value", value: attrValueInput, onChange: (e) => setAttrValueInput(e.target.value), className: "w-32" }), _jsx(Button, { type: "submit", variant: "secondary", children: "Search" })] })] }), _jsx(EntityTable, { data: data?.items, total: data?.total, offset: offset, limit: LIMIT, onPageChange: handlePageChange, isLoading: isLoading }), _jsx(EntityForm, { open: createOpen, onOpenChange: setCreateOpen, isLoading: createEntity.isPending, onSubmit: (formData) => {
                    createEntity.mutate(formData, {
                        onSuccess: () => {
                            setCreateOpen(false);
                            toast.success("Entity created");
                        },
                        onError: () => toast.error("Failed to create entity"),
                    });
                } }), _jsx(BatchUploadDialog, { open: batchOpen, onOpenChange: setBatchOpen, isLoading: batchUpload.isPending, result: batchResult, onUploadCsv: (file) => {
                    batchUpload.mutate(file, {
                        onSuccess: (result) => {
                            setBatchResult(result);
                            toast.success(`Batch upload complete: ${result.created} created, ${result.updated} updated`);
                        },
                        onError: () => toast.error("Batch upload failed"),
                    });
                } })] }));
}
