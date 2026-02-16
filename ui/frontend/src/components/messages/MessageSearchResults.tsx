import { useNavigate } from "react-router";
import { Badge } from "@/components/ui/badge";
import { Pagination, PaginationContent, PaginationItem, PaginationNext, PaginationPrevious } from "@/components/ui/pagination";
import { MessageHighlight } from "./MessageHighlight";
import { formatDateTime } from "@/lib/utils";
import type { ESMessageHit } from "@/lib/types";

interface MessageSearchResultsProps {
  results: ESMessageHit[];
  total: number;
  offset: number;
  limit: number;
  onPageChange: (offset: number) => void;
}

export function MessageSearchResults({
  results,
  total,
  offset,
  limit,
  onPageChange,
}: MessageSearchResultsProps) {
  const navigate = useNavigate();

  if (!results.length) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        No messages match your search.
      </div>
    );
  }

  const from = offset + 1;
  const to = offset + results.length;

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        Showing {from}–{to} of {total} results
      </p>

      <div className="space-y-2">
        {results.map((hit) => {
          const highlights = Object.values(hit.highlights).flat();
          const sender = hit.message.participants.find((p) => p.role === "sender");
          const receiver = hit.message.participants.find((p) => p.role === "receiver" || p.role === "recipient");

          return (
            <div
              key={`${hit.index}/${hit.message.message_id}`}
              className="border rounded-lg p-4 cursor-pointer hover:bg-muted/50 transition-colors space-y-2"
              onClick={() => void navigate(`/messages/${hit.index}/${hit.message.message_id}`)}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Badge variant="outline">{hit.message.channel}</Badge>
                  <span className="text-sm text-muted-foreground">
                    {formatDateTime(hit.message.timestamp)}
                  </span>
                </div>
                {hit.score != null && (
                  <span className="text-xs text-muted-foreground">Score: {hit.score.toFixed(1)}</span>
                )}
              </div>

              {(sender || receiver) && (
                <p className="text-sm">
                  {sender?.name ?? "Unknown"}
                  {receiver && <> → {receiver.name}</>}
                </p>
              )}

              {highlights.length > 0 && (
                <MessageHighlight fragments={highlights.slice(0, 2)} />
              )}
            </div>
          );
        })}
      </div>

      {total > limit && (
        <Pagination>
          <PaginationContent>
            <PaginationItem>
              <PaginationPrevious
                onClick={() => onPageChange(Math.max(0, offset - limit))}
                aria-disabled={offset === 0}
                className={offset === 0 ? "pointer-events-none opacity-50" : "cursor-pointer"}
              />
            </PaginationItem>
            <PaginationItem>
              <PaginationNext
                onClick={() => onPageChange(offset + limit)}
                aria-disabled={offset + limit >= total}
                className={offset + limit >= total ? "pointer-events-none opacity-50" : "cursor-pointer"}
              />
            </PaginationItem>
          </PaginationContent>
        </Pagination>
      )}
    </div>
  );
}
