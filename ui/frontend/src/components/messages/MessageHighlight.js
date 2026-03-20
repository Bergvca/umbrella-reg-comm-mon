import { jsx as _jsx } from "react/jsx-runtime";
function sanitizeHighlight(html) {
    return html.replace(/<(?!\/?(em)( |>))[^>]*>/gi, "");
}
export function MessageHighlight({ fragments }) {
    if (!fragments.length)
        return null;
    const joined = fragments.map(sanitizeHighlight).join(" ... ");
    return (_jsx("span", { className: "text-sm text-muted-foreground [&_em]:font-semibold [&_em]:text-foreground [&_em]:not-italic", dangerouslySetInnerHTML: { __html: joined } }));
}
