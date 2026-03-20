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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Card, CardContent } from "@/components/ui/card";
import type { BatchUploadResult } from "@/lib/types";

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
  const [batchResult, setBatchResult] = useState<BatchUploadResult | null>(null);
  const [searchInput, setSearchInput] = useState(search ?? "");
  const [attrKeyInput, setAttrKeyInput] = useState(attrKey ?? "");
  const [attrValueInput, setAttrValueInput] = useState(attrValue ?? "");

  const createEntity = useCreateEntity();
  const batchUpload = useBatchUploadCsv();

  function buildParams(overrides: Record<string, string | undefined> = {}): Record<string, string> {
    const merged = { entity_type: entityType, search, attr_key: attrKey, attr_value: attrValue, ...overrides };
    const params: Record<string, string> = {};
    for (const [k, v] of Object.entries(merged)) {
      if (v && v !== "all") params[k] = v;
    }
    return params;
  }

  function handleFilterChange(type: string) {
    setSearchParams(buildParams({ entity_type: type === "all" ? undefined : type, offset: undefined }));
  }

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    setSearchParams(buildParams({
      search: searchInput.trim() || undefined,
      attr_key: attrKeyInput.trim() || undefined,
      attr_value: attrValueInput.trim() || undefined,
      offset: undefined,
    }));
  }

  function handlePageChange(newOffset: number) {
    setSearchParams(buildParams({ offset: newOffset > 0 ? String(newOffset) : undefined }));
  }

  if (isError) {
    return (
      <div className="p-6">
        <Card>
          <CardContent className="pt-6 text-center space-y-3">
            <p className="text-muted-foreground">Failed to load entities.</p>
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
        <h1 className="text-2xl font-semibold">Entities</h1>
        {isAdmin && (
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => { setBatchResult(null); setBatchOpen(true); }}>
              Batch Upload
            </Button>
            <Button onClick={() => setCreateOpen(true)}>Create Entity</Button>
          </div>
        )}
      </div>

      <div className="flex gap-3 items-end">
        <Select value={entityType ?? "all"} onValueChange={handleFilterChange}>
          <SelectTrigger className="w-48">
            <SelectValue placeholder="All types" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All types</SelectItem>
            <SelectItem value="person">Person</SelectItem>
            <SelectItem value="organization">Organization</SelectItem>
            <SelectItem value="distribution_list">Distribution List</SelectItem>
          </SelectContent>
        </Select>
        <form onSubmit={handleSearch} className="flex gap-2 items-end">
          <Input
            placeholder="Search by name..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            className="w-48"
          />
          <Input
            placeholder="Attr key"
            value={attrKeyInput}
            onChange={(e) => setAttrKeyInput(e.target.value)}
            className="w-32"
          />
          <Input
            placeholder="Attr value"
            value={attrValueInput}
            onChange={(e) => setAttrValueInput(e.target.value)}
            className="w-32"
          />
          <Button type="submit" variant="secondary">Search</Button>
        </form>
      </div>

      <EntityTable
        data={data?.items}
        total={data?.total}
        offset={offset}
        limit={LIMIT}
        onPageChange={handlePageChange}
        isLoading={isLoading}
      />

      <EntityForm
        open={createOpen}
        onOpenChange={setCreateOpen}
        isLoading={createEntity.isPending}
        onSubmit={(formData) => {
          createEntity.mutate(formData, {
            onSuccess: () => {
              setCreateOpen(false);
              toast.success("Entity created");
            },
            onError: () => toast.error("Failed to create entity"),
          });
        }}
      />

      <BatchUploadDialog
        open={batchOpen}
        onOpenChange={setBatchOpen}
        isLoading={batchUpload.isPending}
        result={batchResult}
        onUploadCsv={(file) => {
          batchUpload.mutate(file, {
            onSuccess: (result) => {
              setBatchResult(result);
              toast.success(`Batch upload complete: ${result.created} created, ${result.updated} updated`);
            },
            onError: () => toast.error("Batch upload failed"),
          });
        }}
      />
    </div>
  );
}
