import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PolicyList } from "@/components/policies/PolicyList";
import { RiskModelList } from "@/components/policies/RiskModelList";
import { useAuthStore } from "@/stores/auth";
import { hasRole } from "@/lib/utils";
export function PoliciesPage() {
    const user = useAuthStore((s) => s.user);
    const canEdit = user ? hasRole(user.roles, "admin") : false;
    return (_jsxs("div", { className: "p-6 space-y-6 max-w-4xl", children: [_jsx("h1", { className: "text-2xl font-semibold", children: "Policies" }), _jsxs(Tabs, { defaultValue: "policies", children: [_jsxs(TabsList, { children: [_jsx(TabsTrigger, { value: "policies", children: "Policies" }), _jsx(TabsTrigger, { value: "risk-models", children: "Risk Models" })] }), _jsx(TabsContent, { value: "policies", className: "pt-4", children: _jsx(PolicyList, { canEdit: canEdit }) }), _jsx(TabsContent, { value: "risk-models", className: "pt-4", children: _jsx(RiskModelList, { canEdit: canEdit }) })] })] }));
}
