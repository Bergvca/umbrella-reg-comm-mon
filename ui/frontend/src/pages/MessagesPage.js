import { jsx as _jsx, Fragment as _Fragment, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from "react";
import { useSearchParams } from "react-router";
import { MessageSearchForm } from "@/components/messages/MessageSearchForm";
import { MessageSearchResults } from "@/components/messages/MessageSearchResults";
import { SearchModeToggle } from "@/components/messages/SearchModeToggle";
import { NLQueryExplainer } from "@/components/messages/NLQueryExplainer";
import { useMessageSearch, useNLSearch } from "@/hooks/useMessages";
import { useAgentModels } from "@/hooks/useAgents";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue, } from "@/components/ui/select";
import { ApiError } from "@/api/client";
import { AlertCircle } from "lucide-react";
const LIMIT = 20;
export function MessagesPage() {
    const [searchParams, setSearchParams] = useSearchParams();
    const mode = (searchParams.get("mode") ?? "keyword");
    const [nlQuery, setNlQuery] = useState(searchParams.get("nlq") ?? "");
    const [nlSubmitted, setNlSubmitted] = useState(searchParams.get("nlq") ?? "");
    const [nlModelId, setNlModelId] = useState(searchParams.get("model") ?? undefined);
    const { data: modelsData } = useAgentModels();
    const models = modelsData?.items ?? [];
    const keywordParams = {
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
    const hasKeywordSearched = !!(keywordParams.q ||
        keywordParams.channel ||
        keywordParams.participant ||
        keywordParams.date_from);
    const { data: keywordData, isLoading: keywordLoading } = useMessageSearch(keywordParams);
    const { data: nlData, isLoading: nlLoading, isError: nlIsError, error: nlError } = useNLSearch(nlSubmitted, nlOffset, LIMIT, nlModelId);
    function nlErrorMessage() {
        if (nlError instanceof ApiError) {
            const body = nlError.body;
            if (body && typeof body.detail === "string")
                return body.detail;
            return `Search failed (HTTP ${nlError.status})`;
        }
        return "Search failed";
    }
    function buildKeywordParams(next, newOffset) {
        const p = { mode: "keyword" };
        if (next.q)
            p.q = next.q;
        if (next.channel)
            p.channel = next.channel;
        if (next.direction)
            p.direction = next.direction;
        if (next.participant)
            p.participant = next.participant;
        if (next.date_from)
            p.date_from = next.date_from;
        if (next.date_to)
            p.date_to = next.date_to;
        if (next.sentiment)
            p.sentiment = next.sentiment;
        if (next.risk_score_min != null)
            p.risk_score_min = String(next.risk_score_min);
        if (newOffset && newOffset > 0)
            p.offset = String(newOffset);
        return p;
    }
    function handleModeChange(newMode) {
        setSearchParams({ mode: newMode });
    }
    function handleNLSearch(e) {
        e.preventDefault();
        if (!nlQuery.trim())
            return;
        setNlSubmitted(nlQuery.trim());
        const p = { mode: "nl", nlq: nlQuery.trim() };
        if (nlModelId)
            p.model = nlModelId;
        setSearchParams(p);
    }
    function handleNLPageChange(newOffset) {
        const p = { mode: "nl" };
        if (nlSubmitted)
            p.nlq = nlSubmitted;
        if (nlModelId)
            p.model = nlModelId;
        if (newOffset > 0)
            p.offset = String(newOffset);
        setSearchParams(p);
    }
    return (_jsxs("div", { className: "p-6 space-y-6 max-w-4xl", children: [_jsx("h1", { className: "text-2xl font-semibold", children: "Message Search" }), _jsx(SearchModeToggle, { mode: mode, onChange: handleModeChange }), mode === "keyword" && (_jsxs(_Fragment, { children: [_jsx(MessageSearchForm, { params: keywordParams, onChange: (next) => setSearchParams(buildKeywordParams(next)), onSubmit: () => setSearchParams(buildKeywordParams(keywordParams)), isLoading: keywordLoading }), hasKeywordSearched && keywordData && (_jsx(MessageSearchResults, { results: keywordData.hits, total: keywordData.total, offset: keywordData.offset, limit: keywordData.limit, onPageChange: (offset) => setSearchParams(buildKeywordParams(keywordParams, offset)) })), hasKeywordSearched && !keywordData && !keywordLoading && (_jsx("div", { className: "text-center py-12 text-muted-foreground", children: "No messages match your search." }))] })), mode === "nl" && (_jsxs(_Fragment, { children: [_jsxs("form", { onSubmit: handleNLSearch, className: "space-y-2", children: [_jsx(Textarea, { rows: 3, value: nlQuery, onChange: (e) => setNlQuery(e.target.value), placeholder: "e.g. Show me high-risk emails from last week about derivatives", className: "resize-none" }), _jsxs("div", { className: "flex items-center justify-between gap-3", children: [_jsxs(Select, { value: nlModelId ?? "", onValueChange: (v) => setNlModelId(v || undefined), children: [_jsx(SelectTrigger, { className: "w-64", children: _jsx(SelectValue, { placeholder: "Model (auto)" }) }), _jsx(SelectContent, { children: models.map((m) => (_jsxs(SelectItem, { value: m.id, children: [m.name, " (", m.provider, ")"] }, m.id))) })] }), _jsx(Button, { type: "submit", disabled: nlLoading || !nlQuery.trim(), children: nlLoading ? "Searching…" : "Search" })] })] }), nlData && (_jsxs(_Fragment, { children: [_jsx(NLQueryExplainer, { explanation: nlData.explanation, generatedQuery: nlData.generated_query }), _jsx(MessageSearchResults, { results: nlData.hits, total: nlData.total, offset: nlData.offset, limit: nlData.limit, onPageChange: handleNLPageChange })] })), nlSubmitted && nlIsError && (_jsxs("div", { className: "rounded-md border border-destructive/50 bg-destructive/10 p-4 flex items-start gap-3", children: [_jsx(AlertCircle, { className: "h-5 w-5 text-destructive shrink-0 mt-0.5" }), _jsxs("div", { children: [_jsx("p", { className: "text-sm font-medium text-destructive", children: "Search failed" }), _jsx("p", { className: "text-sm text-destructive/80 mt-0.5", children: nlErrorMessage() })] })] })), nlSubmitted && !nlData && !nlIsError && !nlLoading && (_jsx("div", { className: "text-center py-12 text-muted-foreground", children: "No messages match your query." }))] }))] }));
}
