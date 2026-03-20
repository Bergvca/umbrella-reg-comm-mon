import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useCreateUser, useUpdateUser } from "@/hooks/useUsers";
export function UserForm({ user, onSuccess, onCancel }) {
    const [email, setEmail] = useState(user?.email ?? "");
    const [username, setUsername] = useState(user?.username ?? "");
    const [password, setPassword] = useState("");
    const createMutation = useCreateUser();
    const updateMutation = useUpdateUser();
    const isPending = createMutation.isPending || updateMutation.isPending;
    function handleSubmit(e) {
        e.preventDefault();
        if (user) {
            updateMutation.mutate({ id: user.id, email: email || undefined }, { onSuccess });
        }
        else {
            createMutation.mutate({ username, email, password }, { onSuccess });
        }
    }
    return (_jsxs("form", { onSubmit: handleSubmit, className: "space-y-4", children: [!user && (_jsxs("div", { className: "space-y-1", children: [_jsx(Label, { children: "Username" }), _jsx(Input, { value: username, onChange: (e) => setUsername(e.target.value), required: true })] })), _jsxs("div", { className: "space-y-1", children: [_jsx(Label, { children: "Email" }), _jsx(Input, { type: "email", value: email, onChange: (e) => setEmail(e.target.value), required: true })] }), !user && (_jsxs("div", { className: "space-y-1", children: [_jsx(Label, { children: "Password" }), _jsx(Input, { type: "password", value: password, onChange: (e) => setPassword(e.target.value), required: true })] })), _jsxs("div", { className: "flex gap-2 justify-end", children: [_jsx(Button, { type: "button", variant: "outline", onClick: onCancel, children: "Cancel" }), _jsx(Button, { type: "submit", disabled: isPending, children: isPending ? "Saving…" : "Save" })] })] }));
}
