import { useState } from "react";
import { ChevronDown, ChevronRight, Info } from "lucide-react";
import { Button } from "@/components/ui/button";

interface Props {
  explanation: string;
  generatedQuery: Record<string, unknown>;
}

export function NLQueryExplainer({ explanation, generatedQuery }: Props) {
  const [showQuery, setShowQuery] = useState(false);

  return (
    <div className="rounded-md border border-blue-200 bg-blue-50 p-3 space-y-2">
      <div className="flex items-start gap-2">
        <Info className="h-4 w-4 text-blue-600 mt-0.5 shrink-0" />
        <p className="text-sm text-blue-800">{explanation || "Query translated by AI."}</p>
      </div>
      <div>
        <Button
          variant="ghost"
          size="sm"
          className="h-6 px-2 text-xs text-blue-700 hover:text-blue-900 hover:bg-blue-100"
          onClick={() => setShowQuery((v) => !v)}
        >
          {showQuery ? (
            <ChevronDown className="h-3 w-3 mr-1" />
          ) : (
            <ChevronRight className="h-3 w-3 mr-1" />
          )}
          {showQuery ? "Hide" : "View"} generated query
        </Button>
        {showQuery && (
          <pre className="mt-2 text-xs bg-white border border-blue-200 rounded p-2 overflow-auto max-h-48">
            {JSON.stringify(generatedQuery, null, 2)}
          </pre>
        )}
      </div>
    </div>
  );
}
