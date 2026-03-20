import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
export function SearchModeToggle({ mode, onChange }) {
    return (_jsx(Tabs, { value: mode, onValueChange: (v) => onChange(v), children: _jsxs(TabsList, { children: [_jsx(TabsTrigger, { value: "keyword", children: "Keyword Search" }), _jsx(TabsTrigger, { value: "nl", children: "Natural Language" })] }) }));
}
