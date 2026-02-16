import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useDecisionStatuses, useCreateDecision } from "@/hooks/useDecisions";
import type { AlertStatus } from "@/lib/types";

interface Props {
  alertId: string;
  alertStatus: AlertStatus;
  onSuccess?: () => void;
}

export function DecisionForm({ alertId, alertStatus, onSuccess }: Props) {
  const [selectedStatusId, setSelectedStatusId] = useState<string>("");
  const [comment, setComment] = useState("");
  const [submitted, setSubmitted] = useState(false);

  const { data: statuses, isLoading: loadingStatuses } = useDecisionStatuses();
  const mutation = useCreateDecision(alertId);

  const isClosed = alertStatus === "closed";

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedStatusId) return;
    mutation.mutate(
      { status_id: selectedStatusId, comment: comment || undefined },
      {
        onSuccess: () => {
          setSelectedStatusId("");
          setComment("");
          setSubmitted(true);
          setTimeout(() => setSubmitted(false), 2000);
          onSuccess?.();
        },
      },
    );
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Submit Decision</CardTitle>
      </CardHeader>
      <CardContent>
        {isClosed ? (
          <p className="text-sm text-muted-foreground">This alert is closed.</p>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="decision-status">Status</Label>
              <Select
                value={selectedStatusId}
                onValueChange={setSelectedStatusId}
                disabled={loadingStatuses || mutation.isPending}
              >
                <SelectTrigger id="decision-status">
                  <SelectValue placeholder="Select a status…" />
                </SelectTrigger>
                <SelectContent>
                  {statuses?.map((s) => (
                    <SelectItem key={s.id} value={s.id}>
                      {s.name}
                      {s.is_terminal ? " (closes alert)" : ""}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="decision-comment">Comment</Label>
              <Textarea
                id="decision-comment"
                placeholder="Add a comment…"
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                disabled={mutation.isPending}
                rows={3}
              />
            </div>

            <Button
              type="submit"
              disabled={!selectedStatusId || mutation.isPending}
              className="w-full sm:w-auto"
            >
              {mutation.isPending ? "Submitting…" : submitted ? "Submitted!" : "Submit Decision"}
            </Button>

            {mutation.isError && (
              <p className="text-sm text-destructive">
                Failed to submit decision. Please try again.
              </p>
            )}
          </form>
        )}
      </CardContent>
    </Card>
  );
}
