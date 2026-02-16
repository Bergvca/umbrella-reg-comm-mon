import { useSearchParams } from "react-router";
import { MessageSearchForm } from "@/components/messages/MessageSearchForm";
import { MessageSearchResults } from "@/components/messages/MessageSearchResults";
import { useMessageSearch } from "@/hooks/useMessages";
import type { MessageSearchParams } from "@/api/messages";

const LIMIT = 20;

export function MessagesPage() {
  const [searchParams, setSearchParams] = useSearchParams();

  const params: MessageSearchParams = {
    q: searchParams.get("q") ?? undefined,
    channel: searchParams.get("channel") ?? undefined,
    direction: searchParams.get("direction") ?? undefined,
    participant: searchParams.get("participant") ?? undefined,
    date_from: searchParams.get("date_from") ?? undefined,
    date_to: searchParams.get("date_to") ?? undefined,
    sentiment: searchParams.get("sentiment") ?? undefined,
    risk_score_min: searchParams.get("risk_score_min") ? Number(searchParams.get("risk_score_min")) : undefined,
    offset: Number(searchParams.get("offset") ?? 0),
    limit: LIMIT,
  };

  const hasSearched = !!(params.q || params.channel || params.participant || params.date_from);
  const { data, isLoading } = useMessageSearch(params);

  function buildParams(next: MessageSearchParams, newOffset?: number): Record<string, string> {
    const p: Record<string, string> = {};
    if (next.q) p.q = next.q;
    if (next.channel) p.channel = next.channel;
    if (next.direction) p.direction = next.direction;
    if (next.participant) p.participant = next.participant;
    if (next.date_from) p.date_from = next.date_from;
    if (next.date_to) p.date_to = next.date_to;
    if (next.sentiment) p.sentiment = next.sentiment;
    if (next.risk_score_min != null) p.risk_score_min = String(next.risk_score_min);
    if (newOffset && newOffset > 0) p.offset = String(newOffset);
    return p;
  }

  return (
    <div className="p-6 space-y-6 max-w-4xl">
      <h1 className="text-2xl font-semibold">Message Search</h1>
      <MessageSearchForm
        params={params}
        onChange={(next) => setSearchParams(buildParams(next))}
        onSubmit={() => setSearchParams(buildParams(params))}
        isLoading={isLoading}
      />
      {hasSearched && data && (
        <MessageSearchResults
          results={data.hits}
          total={data.total}
          offset={data.offset}
          limit={data.limit}
          onPageChange={(offset) => setSearchParams(buildParams(params, offset))}
        />
      )}
      {hasSearched && !data && !isLoading && (
        <div className="text-center py-12 text-muted-foreground">
          No messages match your search.
        </div>
      )}
    </div>
  );
}
