import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Component } from "react";
import { Button } from "@/components/ui/button";
export class ErrorBoundary extends Component {
    constructor(props) {
        super(props);
        this.state = { hasError: false, error: null };
    }
    static getDerivedStateFromError(error) {
        return { hasError: true, error };
    }
    componentDidCatch(error, info) {
        console.error("Uncaught error:", error, info.componentStack);
    }
    render() {
        if (this.state.hasError) {
            return (_jsx("div", { className: "flex min-h-screen items-center justify-center bg-background p-6", children: _jsxs("div", { className: "max-w-md space-y-4 text-center", children: [_jsx("h1", { className: "text-2xl font-semibold", children: "Something went wrong" }), _jsx("p", { className: "text-muted-foreground", children: "An unexpected error occurred. Please try refreshing the page." }), this.state.error && (_jsx("pre", { className: "rounded-md bg-muted p-3 text-left text-xs text-muted-foreground overflow-auto max-h-32", children: this.state.error.message })), _jsx(Button, { onClick: () => {
                                this.setState({ hasError: false, error: null });
                                window.location.href = "/";
                            }, children: "Reload" })] }) }));
        }
        return this.props.children;
    }
}
