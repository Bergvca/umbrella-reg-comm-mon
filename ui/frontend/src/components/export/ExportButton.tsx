import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useState } from "react";
import { buildExportUrl } from "@/api/export";

interface ExportButtonProps {
  type: "alerts" | "messages" | "queue";
  params?: Record<string, string | number | boolean | undefined>;
}

export function ExportButton({ type, params }: ExportButtonProps) {
  const [format, setFormat] = useState<"csv" | "json">("csv");

  function handleExport() {
    const url = buildExportUrl(type, params, format);
    window.open(url, "_blank");
  }

  return (
    <div className="flex gap-2 items-center">
      <Select value={format} onValueChange={(v) => setFormat(v as "csv" | "json")}>
        <SelectTrigger className="w-24 h-8 text-xs">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="csv">CSV</SelectItem>
          <SelectItem value="json">JSON</SelectItem>
        </SelectContent>
      </Select>
      <Button size="sm" variant="outline" onClick={handleExport}>
        Export
      </Button>
    </div>
  );
}
