import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { CHANNELS } from "@/lib/constants";
import type { MessageSearchParams } from "@/api/messages";

interface MessageSearchFormProps {
  params: MessageSearchParams;
  onChange: (params: MessageSearchParams) => void;
  onSubmit: () => void;
  isLoading: boolean;
}

export function MessageSearchForm({ params, onChange, onSubmit, isLoading }: MessageSearchFormProps) {
  const [showFilters, setShowFilters] = useState(false);

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter") onSubmit();
  }

  function clearAll() {
    onChange({ q: params.q });
  }

  return (
    <div className="space-y-3">
      <div className="flex gap-2">
        <Input
          placeholder="Search messages..."
          value={params.q ?? ""}
          onChange={(e) => onChange({ ...params, q: e.target.value })}
          onKeyDown={handleKeyDown}
          className="flex-1"
        />
        <Button onClick={onSubmit} disabled={isLoading}>
          {isLoading ? "Searching..." : "Search"}
        </Button>
        <Button variant="outline" onClick={() => setShowFilters((v) => !v)}>
          {showFilters ? "▲" : "▼"} Filters
        </Button>
      </div>

      {showFilters && (
        <div className="border rounded-lg p-4 space-y-4 bg-muted/30">
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            <div className="space-y-1">
              <Label>Channel</Label>
              <Select
                value={params.channel ?? "all"}
                onValueChange={(v) => onChange({ ...params, channel: v === "all" ? undefined : v })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="All channels" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All channels</SelectItem>
                  {CHANNELS.map((c) => (
                    <SelectItem key={c} value={c}>{c}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1">
              <Label>Direction</Label>
              <Select
                value={params.direction ?? "all"}
                onValueChange={(v) => onChange({ ...params, direction: v === "all" ? undefined : v })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="All" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All</SelectItem>
                  <SelectItem value="inbound">Inbound</SelectItem>
                  <SelectItem value="outbound">Outbound</SelectItem>
                  <SelectItem value="internal">Internal</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1">
              <Label>Sentiment</Label>
              <Select
                value={params.sentiment ?? "all"}
                onValueChange={(v) => onChange({ ...params, sentiment: v === "all" ? undefined : v })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="All" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All</SelectItem>
                  <SelectItem value="positive">Positive</SelectItem>
                  <SelectItem value="neutral">Neutral</SelectItem>
                  <SelectItem value="negative">Negative</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1">
              <Label>Participant</Label>
              <Input
                placeholder="Name or ID"
                value={params.participant ?? ""}
                onChange={(e) => onChange({ ...params, participant: e.target.value || undefined })}
              />
            </div>

            <div className="space-y-1">
              <Label>Date From</Label>
              <Input
                type="date"
                value={params.date_from ?? ""}
                onChange={(e) => onChange({ ...params, date_from: e.target.value || undefined })}
              />
            </div>

            <div className="space-y-1">
              <Label>Date To</Label>
              <Input
                type="date"
                value={params.date_to ?? ""}
                onChange={(e) => onChange({ ...params, date_to: e.target.value || undefined })}
              />
            </div>

            <div className="space-y-1">
              <Label>Min Risk Score</Label>
              <Input
                type="number"
                min={0}
                max={100}
                placeholder="0–100"
                value={params.risk_score_min ?? ""}
                onChange={(e) => onChange({ ...params, risk_score_min: e.target.value ? Number(e.target.value) : undefined })}
              />
            </div>
          </div>

          <Button variant="ghost" size="sm" onClick={clearAll}>
            Clear filters
          </Button>
        </div>
      )}
    </div>
  );
}
