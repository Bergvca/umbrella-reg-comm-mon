import { Badge } from "@/components/ui/badge";
import type { ESMessage } from "@/lib/types";

interface Props {
  message: ESMessage;
}

export function EnrichmentPanel({ message }: Props) {
  const hasAny =
    message.sentiment ||
    message.risk_score !== undefined ||
    message.matched_policies.length > 0 ||
    message.entities.length > 0;

  if (!hasAny) {
    return (
      <p className="text-sm text-muted-foreground">No enrichment data available.</p>
    );
  }

  return (
    <div className="space-y-3 text-sm">
      {(message.sentiment || message.risk_score !== undefined) && (
        <div className="flex flex-wrap gap-4">
          {message.sentiment && (
            <div>
              <span className="text-muted-foreground">Sentiment: </span>
              <span className="font-medium capitalize">{message.sentiment}</span>
              {message.sentiment_score !== undefined && (
                <span className="text-muted-foreground ml-1">
                  ({message.sentiment_score.toFixed(2)})
                </span>
              )}
            </div>
          )}
          {message.risk_score !== undefined && (
            <div>
              <span className="text-muted-foreground">Risk Score: </span>
              <span className="font-medium">{message.risk_score}</span>
            </div>
          )}
        </div>
      )}

      {message.matched_policies.length > 0 && (
        <div>
          <p className="text-muted-foreground mb-1">Matched Policies:</p>
          <p className="font-medium">{message.matched_policies.join(", ")}</p>
        </div>
      )}

      {message.entities.length > 0 && (
        <div>
          <p className="text-muted-foreground mb-1.5">Entities:</p>
          <div className="flex flex-wrap gap-1.5">
            {message.entities.map((e, i) => (
              <Badge key={i} variant="secondary" className="text-xs">
                {e.label}: {e.text}
              </Badge>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
