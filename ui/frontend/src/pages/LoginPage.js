import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useLogin } from "@/hooks/useAuth";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Shield } from "lucide-react";
const loginSchema = z.object({
    username: z.string().min(1, "Username is required"),
    password: z.string().min(1, "Password is required"),
});
export function LoginPage() {
    const loginMutation = useLogin();
    const { register, handleSubmit, formState: { errors }, } = useForm({
        resolver: zodResolver(loginSchema),
    });
    const onSubmit = (data) => {
        loginMutation.mutate(data);
    };
    return (_jsx("div", { className: "flex min-h-screen items-center justify-center bg-muted", children: _jsxs(Card, { className: "w-full max-w-sm", children: [_jsxs(CardHeader, { className: "text-center", children: [_jsx("div", { className: "mx-auto mb-2 flex h-12 w-12 items-center justify-center rounded-full bg-brand-100", children: _jsx(Shield, { className: "h-6 w-6 text-brand-600" }) }), _jsx(CardTitle, { className: "text-xl", children: "Umbrella" }), _jsx("p", { className: "text-sm text-muted-foreground", children: "Communications Monitoring" })] }), _jsx(CardContent, { children: _jsxs("form", { onSubmit: handleSubmit(onSubmit), className: "space-y-4", children: [_jsxs("div", { className: "space-y-2", children: [_jsx(Label, { htmlFor: "username", children: "Username" }), _jsx(Input, { id: "username", autoComplete: "username", autoFocus: true, ...register("username") }), errors.username && (_jsx("p", { className: "text-sm text-destructive", children: errors.username.message }))] }), _jsxs("div", { className: "space-y-2", children: [_jsx(Label, { htmlFor: "password", children: "Password" }), _jsx(Input, { id: "password", type: "password", autoComplete: "current-password", ...register("password") }), errors.password && (_jsx("p", { className: "text-sm text-destructive", children: errors.password.message }))] }), loginMutation.isError && (_jsx("p", { className: "text-sm text-destructive", children: "Invalid username or password" })), _jsx(Button, { type: "submit", className: "w-full", disabled: loginMutation.isPending, children: loginMutation.isPending ? "Signing in..." : "Sign in" })] }) })] }) }));
}
