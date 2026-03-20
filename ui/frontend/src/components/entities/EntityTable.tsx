import { useNavigate } from "react-router";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { formatRelative } from "@/lib/utils";
import type { EntityOut } from "@/lib/types";

interface Props {
  data?: EntityOut[];
  total?: number;
  offset: number;
  limit: number;
  onPageChange: (offset: number) => void;
  isLoading?: boolean;
}

const TYPE_VARIANT: Record<string, "default" | "secondary" | "outline"> = {
  person: "default",
  organization: "secondary",
  distribution_list: "outline",
};

export function EntityTable({ data, total = 0, offset, limit, onPageChange, isLoading }: Props) {
  const navigate = useNavigate();
  const currentPage = Math.floor(offset / limit) + 1;
  const totalPages = Math.max(1, Math.ceil(total / limit));

  const headers = (
    <TableRow>
      <TableHead>Name</TableHead>
      <TableHead>Type</TableHead>
      <TableHead>Handles</TableHead>
      <TableHead>Created</TableHead>
    </TableRow>
  );

  if (isLoading) {
    return (
      <div className="rounded-md border">
        <Table>
          <TableHeader>{headers}</TableHeader>
          <TableBody>
            {Array.from({ length: 6 }).map((_, i) => (
              <TableRow key={i}>
                <TableCell><Skeleton className="h-5 w-40" /></TableCell>
                <TableCell><Skeleton className="h-5 w-24" /></TableCell>
                <TableCell><Skeleton className="h-5 w-32" /></TableCell>
                <TableCell><Skeleton className="h-5 w-24" /></TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div className="rounded-md border">
        <Table>
          <TableHeader>{headers}</TableHeader>
          <TableBody>
            <TableRow>
              <TableCell colSpan={4} className="text-center py-8 text-muted-foreground">
                No entities found.
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="rounded-md border">
        <Table>
          <TableHeader>{headers}</TableHeader>
          <TableBody>
            {data.map((entity) => (
              <TableRow
                key={entity.id}
                className="cursor-pointer hover:bg-muted/50"
                onClick={() => void navigate(`/entities/${entity.id}`)}
              >
                <TableCell className="font-medium">{entity.display_name}</TableCell>
                <TableCell>
                  <Badge variant={TYPE_VARIANT[entity.entity_type] ?? "outline"}>
                    {entity.entity_type}
                  </Badge>
                </TableCell>
                <TableCell className="text-muted-foreground text-sm">
                  {entity.handles.length > 0
                    ? entity.handles.map((h) => h.handle_value).join(", ")
                    : "—"}
                </TableCell>
                <TableCell className="text-muted-foreground text-sm">
                  {formatRelative(entity.created_at)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>
          Showing {offset + 1}–{Math.min(offset + limit, total)} of {total}
        </span>
        <Pagination>
          <PaginationContent>
            <PaginationItem>
              <PaginationPrevious
                onClick={() => onPageChange(Math.max(0, offset - limit))}
                aria-disabled={currentPage <= 1}
                className={currentPage <= 1 ? "pointer-events-none opacity-50" : "cursor-pointer"}
              />
            </PaginationItem>
            <PaginationItem>
              <span className="px-3 py-1">
                Page {currentPage} of {totalPages}
              </span>
            </PaginationItem>
            <PaginationItem>
              <PaginationNext
                onClick={() => onPageChange(offset + limit)}
                aria-disabled={currentPage >= totalPages}
                className={currentPage >= totalPages ? "pointer-events-none opacity-50" : "cursor-pointer"}
              />
            </PaginationItem>
          </PaginationContent>
        </Pagination>
      </div>
    </div>
  );
}
