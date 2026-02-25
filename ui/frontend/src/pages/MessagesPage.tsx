import { useState } from "react";
import { useSearchParams } from "react-router";
import { MessageSearchForm } from "@/components/messages/MessageSearchForm";
import { MessageSearchResults } from "@/components/messages/MessageSearchResults";
import { SearchModeToggle } from "@/components/messages/SearchModeToggle";
import { NLQueryExplainer } from "@/components/messages/NLQueryExplainer";
import { useMessageSearch, useNLSearch } from "@/hooks/useMessages";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/api/client";
import { AlertCircle } from "lucide-react";
import type { MessageSearchParams } from "@/api/messages";

const LIMIT = 20;

type SearchMode = "keyword" | "nl";

export function MessagesPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const mode = (searchParams.get("mode") ?? "keyword") as SearchMode;
  const [nlQuery, setNlQuery] = useState(searchParams.get("nlq") ?? "");
  const [nlSubmitted, setNlSubmitted] = useState(searchParams.get("nlq") ?? "");

  const keywordParams: MessageSearchParams = {
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

  const nlOffset = Number(searchParams.get("offset") ?? 0);

  const hasKeywordSearched = !!(
    keywordParams.q ||
    keywordParams.channel ||
    keywordParams.participant ||
    keywordParams.date_from
  );

  const { data: keywordData, isLoading: keywordLoading } = useMessageSearch(keywordParams);
  const { data: nlData, isLoading: nlLoading, isError: nlIsError, error: nlError } = useNLSearch(nlSubmitted, nlOffset, LIMIT);

  function nlErrorMessage(): string {
    if (nlError instanceof ApiError) {
      const body = nlError.body as Record<string, unknown> | null;
      if (body && typeof body.detail === "string") return body.detail;
      return `Search failed (HTTP ${nlError.status})`;
    }
    return "Search failed";
  }

  function buildKeywordParams(next: MessageSearchParams, newOffset?: number): Record<string, string> {
    const p: Record<string, string> = { mode: "keyword" };
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

  function handleModeChange(newMode: SearchMode) {
    setSearchParams({ mode: newMode });
  }

  function handleNLSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!nlQuery.trim()) return;
    setNlSubmitted(nlQuery.trim());
    setSearchParams({ mode: "nl", nlq: nlQuery.trim() });
  }

  function handleNLPageChange(newOffset: number) {
    const p: Record<string, string> = { mode: "nl" };
    if (nlSubmitted) p.nlq = nlSubmitted;
    if (newOffset > 0) p.offset = String(newOffset);
    setSearchParams(p);
  }

  return (
    <div className="p-6 space-y-6 max-w-4xl">
      <h1 className="text-2xl font-semibold">Message Search</h1>

      <SearchModeToggle mode={mode} onChange={handleModeChange} />

      {mode === "keyword" && (
        <>
          <MessageSearchForm
            params={keywordParams}
            onChange={(next) => setSearchParams(buildKeywordParams(next))}
            onSubmit={() => setSearchParams(buildKeywordParams(keywordParams))}
            isLoading={keywordLoading}
          />
          {hasKeywordSearched && keywordData && (
            <MessageSearchResults
              results={keywordData.hits}
              total={keywordData.total}
              offset={keywordData.offset}
              limit={keywordData.limit}
              onPageChange={(offset) => setSearchParams(buildKeywordParams(keywordParams, offset))}
            />
          )}
          {hasKeywordSearched && !keywordData && !keywordLoading && (
            <div className="text-center py-12 text-muted-foreground">
              No messages match your search.
            </div>
          )}
        </>
      )}

      {mode === "nl" && (
        <>
          <form onSubmit={handleNLSearch} className="space-y-2">
            <Textarea
              rows={3}
              value={nlQuery}
              onChange={(e) => setNlQuery(e.target.value)}
              placeholder="e.g. Show me high-risk emails from last week about derivatives"
              className="resize-none"
            />
            <div className="flex justify-end">
              <Button type="submit" disabled={nlLoading || !nlQuery.trim()}>
                {nlLoading ? "Searching…" : "Search"}
              </Button>
            </div>
          </form>

          {nlData && (
            <>
              <NLQueryExplainer
                explanation={nlData.explanation}
                generatedQuery={nlData.generated_query}
              />
              <MessageSearchResults
                results={nlData.hits}
                total={nlData.total}
                offset={nlData.offset}
                limit={nlData.limit}
                onPageChange={handleNLPageChange}
              />
            </>
          )}

          {nlSubmitted && nlIsError && (
            <div className="rounded-md border border-destructive/50 bg-destructive/10 p-4 flex items-start gap-3">
              <AlertCircle className="h-5 w-5 text-destructive shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-destructive">Search failed</p>
                <p className="text-sm text-destructive/80 mt-0.5">{nlErrorMessage()}</p>
              </div>
            </div>
          )}

          {nlSubmitted && !nlData && !nlIsError && !nlLoading && (
            <div className="text-center py-12 text-muted-foreground">
              No messages match your query.
            </div>
          )}
        </>
      )}
    </div>
  );
}
