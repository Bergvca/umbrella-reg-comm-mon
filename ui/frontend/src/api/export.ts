const BASE_URL = "/api/v1";

export function buildExportUrl(
  type: string,
  params: Record<string, string | number | boolean | undefined> = {},
  format: "csv" | "json" = "csv",
): string {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v != null) sp.set(k, String(v));
  }
  sp.set("format", format);
  return `${BASE_URL}/export/${type}?${sp.toString()}`;
}
