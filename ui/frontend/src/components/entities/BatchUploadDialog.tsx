import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { BatchUploadResult } from "@/lib/types";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onUploadCsv: (file: File) => void;
  isLoading?: boolean;
  result?: BatchUploadResult | null;
}

export function BatchUploadDialog({ open, onOpenChange, onUploadCsv, isLoading, result }: Props) {
  const [file, setFile] = useState<File | null>(null);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (file) onUploadCsv(file);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Batch Upload Entities</DialogTitle>
          <DialogDescription>
            Upload a CSV file with columns: display_name, entity_type, handle_type,
            handle_value, is_primary. Additional columns are treated as attributes.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="csv_file">CSV File</Label>
            <Input
              id="csv_file"
              type="file"
              accept=".csv"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </div>

          {result && (
            <div className="rounded-md border p-3 text-sm space-y-1">
              <p>Created: {result.created}</p>
              <p>Updated: {result.updated}</p>
              {result.errors.length > 0 && (
                <div className="text-destructive">
                  <p>Errors:</p>
                  <ul className="list-disc pl-4">
                    {result.errors.map((err, i) => (
                      <li key={i}>{err}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Close
            </Button>
            <Button type="submit" disabled={isLoading || !file}>
              {isLoading ? "Uploading..." : "Upload"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
