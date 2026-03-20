import { useState } from "react";
import { useParams, useNavigate, Link } from "react-router";
import { toast } from "sonner";
import {
  useEntity,
  useEntityMessages,
  useEntityAlerts,
  useDeleteEntity,
  useAddHandle,
  useRemoveHandle,
  useAddAttribute,
  useRemoveAttribute,
} from "@/hooks/useEntities";
import { useAuthStore } from "@/stores/auth";
import { hasRole, formatRelative } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { Trash2 } from "lucide-react";

export function EntityDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const isAdmin = user ? hasRole(user.roles, "admin") : false;

  const { data: entity, isLoading, isError } = useEntity(id!);
  const { data: messagesData, isLoading: messagesLoading } = useEntityMessages(id!, { limit: 10 });
  const { data: alertsData, isLoading: alertsLoading } = useEntityAlerts(id!);
  const deleteEntity = useDeleteEntity();
  const addHandle = useAddHandle();
  const removeHandle = useRemoveHandle();
  const addAttribute = useAddAttribute();
  const removeAttribute = useRemoveAttribute();

  // Handle form state
  const [handleType, setHandleType] = useState("email");
  const [handleValue, setHandleValue] = useState("");

  // Attribute form state
  const [attrKey, setAttrKey] = useState("");
  const [attrValue, setAttrValue] = useState("");

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  if (isError || !entity) {
    return (
      <div className="p-6">
        <Card>
          <CardContent className="pt-6 text-center text-muted-foreground">
            Entity not found.
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold">{entity.display_name}</h1>
          <div className="flex gap-2 items-center text-sm text-muted-foreground">
            <Badge variant="secondary">{entity.entity_type}</Badge>
            <span>Created {formatRelative(entity.created_at)}</span>
          </div>
        </div>
        {isAdmin && (
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button variant="destructive" size="sm">Delete Entity</Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Delete entity?</AlertDialogTitle>
                <AlertDialogDescription>
                  This will permanently delete {entity.display_name} and all associated handles and attributes.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction
                  onClick={() =>
                    deleteEntity.mutate(entity.id, {
                      onSuccess: () => {
                        toast.success("Entity deleted");
                        void navigate("/entities");
                      },
                    })
                  }
                >
                  Delete
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        )}
      </div>

      {/* Handles */}
      <Card>
        <CardHeader>
          <CardTitle>Handles</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Type</TableHead>
                <TableHead>Value</TableHead>
                <TableHead>Primary</TableHead>
                {isAdmin && <TableHead className="w-12" />}
              </TableRow>
            </TableHeader>
            <TableBody>
              {entity.handles.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={isAdmin ? 4 : 3} className="text-center text-muted-foreground py-4">
                    No handles.
                  </TableCell>
                </TableRow>
              ) : (
                entity.handles.map((h) => (
                  <TableRow key={h.id}>
                    <TableCell>
                      <Badge variant="outline">{h.handle_type}</Badge>
                    </TableCell>
                    <TableCell className="font-mono text-sm">{h.handle_value}</TableCell>
                    <TableCell>{h.is_primary ? "Yes" : "No"}</TableCell>
                    {isAdmin && (
                      <TableCell>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() =>
                            removeHandle.mutate(
                              { entityId: entity.id, handleId: h.id },
                              { onSuccess: () => toast.success("Handle removed") },
                            )
                          }
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </TableCell>
                    )}
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>

          {isAdmin && (
            <form
              className="flex gap-2 items-end"
              onSubmit={(e) => {
                e.preventDefault();
                if (!handleValue.trim()) return;
                addHandle.mutate(
                  { entityId: entity.id, body: { handle_type: handleType, handle_value: handleValue.trim() } },
                  {
                    onSuccess: () => {
                      setHandleValue("");
                      toast.success("Handle added");
                    },
                    onError: () => toast.error("Failed to add handle"),
                  },
                );
              }}
            >
              <Select value={handleType} onValueChange={setHandleType}>
                <SelectTrigger className="w-40">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="email">Email</SelectItem>
                  <SelectItem value="teams_id">Teams ID</SelectItem>
                  <SelectItem value="bloomberg_uuid">Bloomberg UUID</SelectItem>
                  <SelectItem value="turret_extension">Turret Extension</SelectItem>
                </SelectContent>
              </Select>
              <Input
                placeholder="Handle value"
                value={handleValue}
                onChange={(e) => setHandleValue(e.target.value)}
                className="flex-1"
              />
              <Button type="submit" size="sm" disabled={addHandle.isPending}>
                Add
              </Button>
            </form>
          )}
        </CardContent>
      </Card>

      {/* Attributes */}
      <Card>
        <CardHeader>
          <CardTitle>Attributes</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Key</TableHead>
                <TableHead>Value</TableHead>
                <TableHead>Valid From</TableHead>
                <TableHead>Valid To</TableHead>
                {isAdmin && <TableHead className="w-12" />}
              </TableRow>
            </TableHeader>
            <TableBody>
              {entity.attributes.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={isAdmin ? 5 : 4} className="text-center text-muted-foreground py-4">
                    No attributes.
                  </TableCell>
                </TableRow>
              ) : (
                entity.attributes.map((a) => (
                  <TableRow key={a.id}>
                    <TableCell className="font-medium">{a.attr_key}</TableCell>
                    <TableCell>{a.attr_value}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {a.valid_from ? formatRelative(a.valid_from) : "—"}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {a.valid_to ? formatRelative(a.valid_to) : "—"}
                    </TableCell>
                    {isAdmin && (
                      <TableCell>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() =>
                            removeAttribute.mutate(
                              { entityId: entity.id, attrId: a.id },
                              { onSuccess: () => toast.success("Attribute removed") },
                            )
                          }
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </TableCell>
                    )}
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>

          {isAdmin && (
            <form
              className="flex gap-2 items-end"
              onSubmit={(e) => {
                e.preventDefault();
                if (!attrKey.trim() || !attrValue.trim()) return;
                addAttribute.mutate(
                  { entityId: entity.id, body: { attr_key: attrKey.trim(), attr_value: attrValue.trim() } },
                  {
                    onSuccess: () => {
                      setAttrKey("");
                      setAttrValue("");
                      toast.success("Attribute added");
                    },
                    onError: () => toast.error("Failed to add attribute"),
                  },
                );
              }}
            >
              <div className="space-y-1">
                <Label className="text-xs">Key</Label>
                <Input
                  placeholder="e.g. department"
                  value={attrKey}
                  onChange={(e) => setAttrKey(e.target.value)}
                  className="w-40"
                />
              </div>
              <div className="space-y-1 flex-1">
                <Label className="text-xs">Value</Label>
                <Input
                  placeholder="e.g. Trading"
                  value={attrValue}
                  onChange={(e) => setAttrValue(e.target.value)}
                />
              </div>
              <Button type="submit" size="sm" disabled={addAttribute.isPending}>
                Add
              </Button>
            </form>
          )}
        </CardContent>
      </Card>

      {/* Messages */}
      <Card>
        <CardHeader>
          <CardTitle>
            Recent Messages
            {messagesData && messagesData.total > 0 && (
              <span className="ml-2 text-sm font-normal text-muted-foreground">
                ({messagesData.total} total)
              </span>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {messagesLoading ? (
            <Skeleton className="h-24 w-full" />
          ) : !messagesData?.items.length ? (
            <p className="text-sm text-muted-foreground text-center py-4">No messages found.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Timestamp</TableHead>
                  <TableHead>Channel</TableHead>
                  <TableHead>Subject / Preview</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {messagesData.items.map((hit) => (
                  <TableRow key={`${hit.index}/${hit.message.message_id}`}>
                    <TableCell className="text-sm whitespace-nowrap">
                      {formatRelative(hit.message.timestamp)}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">{hit.message.channel}</Badge>
                    </TableCell>
                    <TableCell>
                      <Link
                        to={`/messages/${hit.index}/${hit.message.message_id}`}
                        className="text-sm hover:underline"
                      >
                        {hit.message.body_text?.slice(0, 100) ?? "—"}
                      </Link>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Alerts */}
      <Card>
        <CardHeader>
          <CardTitle>Alerts</CardTitle>
        </CardHeader>
        <CardContent>
          {alertsLoading ? (
            <Skeleton className="h-24 w-full" />
          ) : !alertsData?.length ? (
            <p className="text-sm text-muted-foreground text-center py-4">No alerts linked.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Created</TableHead>
                  <TableHead>Rule</TableHead>
                  <TableHead>Severity</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {alertsData.map((a) => (
                  <TableRow key={a.id}>
                    <TableCell className="text-sm whitespace-nowrap">
                      {formatRelative(a.created_at)}
                    </TableCell>
                    <TableCell className="text-sm">
                      <Link
                        to={`/messages/${a.es_index}/${a.es_document_id}`}
                        className="hover:underline"
                      >
                        {a.rule_name ?? a.name}
                      </Link>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">{a.severity}</Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant="secondary">{a.status}</Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
