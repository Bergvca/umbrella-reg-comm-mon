import { useNavigate } from "react-router";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { MyQueueList } from "@/components/queues/MyQueueList";
import { CreateQueueDialog } from "@/components/queues/CreateQueueDialog";
import { useQueues } from "@/hooks/useQueues";
import { useAuthStore } from "@/stores/auth";
import { hasRole } from "@/lib/utils";
import { formatRelative } from "@/lib/utils";

export function QueuesPage() {
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const isSupervisor = user ? hasRole(user.roles, "supervisor") : false;

  const { data: queuesData, isLoading: loadingQueues } = useQueues();

  if (!isSupervisor) {
    return (
      <div className="p-6 space-y-4">
        <h1 className="text-2xl font-semibold">My Queue</h1>
        <MyQueueList />
      </div>
    );
  }

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Review Queues</h1>
        <CreateQueueDialog />
      </div>
      <Tabs defaultValue="my-queue">
        <TabsList>
          <TabsTrigger value="my-queue">My Batches</TabsTrigger>
          <TabsTrigger value="all-queues">All Queues</TabsTrigger>
        </TabsList>

        <TabsContent value="my-queue" className="mt-4">
          <MyQueueList />
        </TabsContent>

        <TabsContent value="all-queues" className="mt-4">
          {loadingQueues ? (
            <div className="space-y-2">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : (
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Batches</TableHead>
                    <TableHead>Total Items</TableHead>
                    <TableHead>Created</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {!queuesData?.items?.length ? (
                    <TableRow>
                      <TableCell colSpan={4} className="text-center py-8 text-muted-foreground">
                        No queues found.
                      </TableCell>
                    </TableRow>
                  ) : (
                    queuesData.items.map((q) => (
                      <TableRow
                        key={q.id}
                        className="cursor-pointer hover:bg-muted/50"
                        onClick={() => void navigate(`/queues/${q.id}`)}
                      >
                        <TableCell className="font-medium">{q.name}</TableCell>
                        <TableCell className="text-muted-foreground">—</TableCell>
                        <TableCell className="text-muted-foreground">—</TableCell>
                        <TableCell className="text-muted-foreground text-sm">
                          {formatRelative(q.created_at)}
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
