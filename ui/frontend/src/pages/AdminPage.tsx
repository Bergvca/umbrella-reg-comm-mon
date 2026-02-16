import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { UserTable } from "@/components/admin/UserTable";
import { GroupTable } from "@/components/admin/GroupTable";
import { DecisionStatusTable } from "@/components/admin/DecisionStatusTable";

export function AdminPage() {
  return (
    <div className="p-6 space-y-6 max-w-5xl">
      <h1 className="text-2xl font-semibold">Administration</h1>
      <Tabs defaultValue="users">
        <TabsList>
          <TabsTrigger value="users">Users</TabsTrigger>
          <TabsTrigger value="groups">Groups</TabsTrigger>
          <TabsTrigger value="queues">Decision Queues</TabsTrigger>
        </TabsList>
        <TabsContent value="users" className="pt-4">
          <UserTable />
        </TabsContent>
        <TabsContent value="groups" className="pt-4">
          <GroupTable />
        </TabsContent>
        <TabsContent value="queues" className="pt-4">
          <DecisionStatusTable />
        </TabsContent>
      </Tabs>
    </div>
  );
}
