import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (data: {
    display_name: string;
    entity_type: string;
    handles: { handle_type: string; handle_value: string; is_primary: boolean }[];
  }) => void;
  isLoading?: boolean;
}

export function EntityForm({ open, onOpenChange, onSubmit, isLoading }: Props) {
  const [displayName, setDisplayName] = useState("");
  const [entityType, setEntityType] = useState("person");
  const [handleType, setHandleType] = useState("email");
  const [handleValue, setHandleValue] = useState("");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const handles = handleValue.trim()
      ? [{ handle_type: handleType, handle_value: handleValue.trim(), is_primary: true }]
      : [];
    onSubmit({ display_name: displayName, entity_type: entityType, handles });
    setDisplayName("");
    setEntityType("person");
    setHandleType("email");
    setHandleValue("");
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Create Entity</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="display_name">Display Name</Label>
            <Input
              id="display_name"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="entity_type">Type</Label>
            <Select value={entityType} onValueChange={setEntityType}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="person">Person</SelectItem>
                <SelectItem value="organization">Organization</SelectItem>
                <SelectItem value="distribution_list">Distribution List</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="handle_type">Handle Type</Label>
            <Select value={handleType} onValueChange={setHandleType}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="email">Email</SelectItem>
                <SelectItem value="teams_id">Teams ID</SelectItem>
                <SelectItem value="bloomberg_uuid">Bloomberg UUID</SelectItem>
                <SelectItem value="turret_extension">Turret Extension</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="handle_value">Handle Value</Label>
            <Input
              id="handle_value"
              value={handleValue}
              onChange={(e) => setHandleValue(e.target.value)}
              placeholder="e.g. jane.smith@acme.com"
            />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={isLoading || !displayName.trim()}>
              {isLoading ? "Creating..." : "Create"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
