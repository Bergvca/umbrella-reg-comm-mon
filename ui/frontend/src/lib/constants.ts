export const SEVERITY_LEVELS = ["critical", "high", "medium", "low"] as const;

export const SEVERITY_COLORS: Record<string, string> = {
  critical: "text-severity-critical bg-severity-critical/10",
  high: "text-severity-high bg-severity-high/10",
  medium: "text-severity-medium bg-severity-medium/10",
  low: "text-severity-low bg-severity-low/10",
};

export const ALERT_STATUSES = ["open", "in_review", "closed"] as const;

export const CHANNELS = [
  "email",
  "teams_chat",
  "teams_calls",
  "bloomberg_chat",
  "bloomberg_email",
  "unigy_turret",
] as const;

export const ROLES = {
  ADMIN: "admin",
  SUPERVISOR: "supervisor",
  REVIEWER: "reviewer",
} as const;

/** Role hierarchy — admin > supervisor > reviewer */
export const ROLE_HIERARCHY: Record<string, number> = {
  admin: 3,
  supervisor: 2,
  reviewer: 1,
};
