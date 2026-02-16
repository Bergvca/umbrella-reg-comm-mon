interface MessageHighlightProps {
  fragments: string[];
}

function sanitizeHighlight(html: string): string {
  return html.replace(/<(?!\/?(em)( |>))[^>]*>/gi, "");
}

export function MessageHighlight({ fragments }: MessageHighlightProps) {
  if (!fragments.length) return null;
  const joined = fragments.map(sanitizeHighlight).join(" ... ");
  return (
    <span
      className="text-sm text-muted-foreground [&_em]:font-semibold [&_em]:text-foreground [&_em]:not-italic"
      dangerouslySetInnerHTML={{ __html: joined }}
    />
  );
}
