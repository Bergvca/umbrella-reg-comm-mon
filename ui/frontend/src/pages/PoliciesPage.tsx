import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PolicyList } from "@/components/policies/PolicyList";
import { RiskModelList } from "@/components/policies/RiskModelList";
import { useAuthStore } from "@/stores/auth";
import { hasRole } from "@/lib/utils";

export function PoliciesPage() {
  const user = useAuthStore((s) => s.user);
  const canEdit = user ? hasRole(user.roles, "admin") : false;

  return (
    <div className="p-6 space-y-6 max-w-4xl">
      <h1 className="text-2xl font-semibold">Policies</h1>
      <Tabs defaultValue="policies">
        <TabsList>
          <TabsTrigger value="policies">Policies</TabsTrigger>
          <TabsTrigger value="risk-models">Risk Models</TabsTrigger>
        </TabsList>
        <TabsContent value="policies" className="pt-4">
          <PolicyList canEdit={canEdit} />
        </TabsContent>
        <TabsContent value="risk-models" className="pt-4">
          <RiskModelList canEdit={canEdit} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
