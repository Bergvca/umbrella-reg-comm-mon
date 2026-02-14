# Phase 4 — Frontend Foundation + Login

## Goal

Scaffold the React SPA, wire up authentication against the existing backend API, build the app shell (sidebar + header), and deliver a dashboard page showing real alert metrics. At the end of this phase the frontend builds, deploys, and a compliance officer can log in and see a live dashboard.

---

## Prerequisites

- Backend Phases 1–3 complete (all `/api/v1/*` endpoints deployed)
- PostgreSQL with seed data (users, roles, groups, some alerts)
- Elasticsearch with indexed messages and alerts
- Node.js 22+ installed locally

---

## 1. Project Scaffold

### 1.1 Initialize Vite + React + TypeScript

```bash
cd ui/frontend
npm create vite@latest . -- --template react-ts
```

This generates the standard Vite scaffold. We then strip the default boilerplate (`App.css`, `assets/`, demo content) and restructure to match the directory layout defined in `docs/ui-layer-plan.md` Section 3.

### 1.2 `package.json` — Dependencies

```jsonc
{
  "name": "umbrella-ui",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "lint": "eslint . --ext ts,tsx --report-unused-disable-directives --max-warnings 0",
    "test": "vitest",
    "test:ui": "vitest --ui"
  },
  "dependencies": {
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "react-router": "^7.0.0",
    "@tanstack/react-query": "^5.0.0",
    "zustand": "^5.0.0",
    "react-hook-form": "^7.54.0",
    "@hookform/resolvers": "^4.0.0",
    "zod": "^3.24.0",
    "recharts": "^2.15.0",
    "clsx": "^2.1.0",
    "tailwind-merge": "^3.0.0",
    "class-variance-authority": "^0.7.0",
    "@radix-ui/react-slot": "^1.1.0",
    "@radix-ui/react-dialog": "^1.1.0",
    "@radix-ui/react-dropdown-menu": "^2.1.0",
    "@radix-ui/react-avatar": "^1.1.0",
    "@radix-ui/react-separator": "^1.1.0",
    "@radix-ui/react-tooltip": "^1.1.0",
    "@radix-ui/react-select": "^2.1.0",
    "@radix-ui/react-label": "^2.1.0",
    "lucide-react": "^0.474.0",
    "date-fns": "^4.1.0"
  },
  "devDependencies": {
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "@vitejs/plugin-react": "^4.3.0",
    "typescript": "~5.7.0",
    "vite": "^6.1.0",
    "vitest": "^3.0.0",
    "@testing-library/react": "^16.0.0",
    "@testing-library/jest-dom": "^6.6.0",
    "@testing-library/user-event": "^14.5.0",
    "jsdom": "^26.0.0",
    "tailwindcss": "^4.0.0",
    "@tailwindcss/vite": "^4.0.0",
    "eslint": "^9.0.0",
    "eslint-plugin-react-hooks": "^5.0.0",
    "@eslint/js": "^9.0.0",
    "typescript-eslint": "^8.0.0",
    "@tanstack/react-query-devtools": "^5.0.0",
    "msw": "^2.7.0"
  }
}
```

**Key decisions:**
- **Tailwind v4** — uses the Vite plugin (`@tailwindcss/vite`) instead of PostCSS; config is CSS-native via `@theme` directives
- **shadcn/ui** — not installed as a package; components are copied into `src/components/ui/` via `npx shadcn@latest init` then selectively adding components with `npx shadcn@latest add button card input label select dialog dropdown-menu avatar separator tooltip`
- **lucide-react** — icon library used by shadcn/ui
- **date-fns** — lightweight date formatting (no moment.js)
- **msw** — Mock Service Worker for testing (intercepts fetch in tests)
- **No axios** — use native `fetch` with a thin wrapper; avoids extra dependency

### 1.3 `vite.config.ts`

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
    css: true,
  },
});
```

**Proxy config** — during local dev, `/api/*` requests are forwarded to the FastAPI backend on port 8000. In production, nginx handles this routing.

### 1.4 `tsconfig.json`

```jsonc
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "forceConsistentCasingInFileNames": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["src", "tests"]
}
```

### 1.5 `index.html`

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Umbrella — Communications Monitoring</title>
    <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

### 1.6 Tailwind CSS v4 Setup

Tailwind v4 is CSS-native. Create `src/index.css`:

```css
@import "tailwindcss";

@theme {
  /* Brand palette — neutral, professional compliance UI */
  --color-brand-50: oklch(0.97 0.01 250);
  --color-brand-100: oklch(0.93 0.02 250);
  --color-brand-200: oklch(0.87 0.04 250);
  --color-brand-300: oklch(0.77 0.06 250);
  --color-brand-400: oklch(0.65 0.08 250);
  --color-brand-500: oklch(0.55 0.10 250);
  --color-brand-600: oklch(0.45 0.10 250);
  --color-brand-700: oklch(0.35 0.08 250);
  --color-brand-800: oklch(0.27 0.06 250);
  --color-brand-900: oklch(0.20 0.04 250);

  /* Severity colors (consistent with compliance UI conventions) */
  --color-severity-critical: oklch(0.55 0.22 25);
  --color-severity-high: oklch(0.65 0.20 40);
  --color-severity-medium: oklch(0.75 0.15 80);
  --color-severity-low: oklch(0.70 0.12 145);

  /* Sidebar width */
  --sidebar-width: 16rem;
  --sidebar-width-collapsed: 4rem;

  /* Font */
  --font-sans: "Inter", ui-sans-serif, system-ui, sans-serif;
  --font-mono: "JetBrains Mono", ui-monospace, monospace;
}

/* shadcn/ui CSS variables — maps to Tailwind v4 theme tokens */
@layer base {
  :root {
    --background: 0 0% 100%;
    --foreground: 222.2 84% 4.9%;
    --card: 0 0% 100%;
    --card-foreground: 222.2 84% 4.9%;
    --popover: 0 0% 100%;
    --popover-foreground: 222.2 84% 4.9%;
    --primary: 222.2 47.4% 11.2%;
    --primary-foreground: 210 40% 98%;
    --secondary: 210 40% 96%;
    --secondary-foreground: 222.2 47.4% 11.2%;
    --muted: 210 40% 96%;
    --muted-foreground: 215.4 16.3% 46.9%;
    --accent: 210 40% 96%;
    --accent-foreground: 222.2 47.4% 11.2%;
    --destructive: 0 84.2% 60.2%;
    --destructive-foreground: 210 40% 98%;
    --border: 214.3 31.8% 91.4%;
    --input: 214.3 31.8% 91.4%;
    --ring: 222.2 84% 4.9%;
    --radius: 0.5rem;
  }
}
```

### 1.7 shadcn/ui Initialization

```bash
npx shadcn@latest init
# Select: New York style, Neutral color, CSS variables: yes
```

Then add the components needed for Phase 4:

```bash
npx shadcn@latest add button card input label separator avatar \
  dropdown-menu dialog tooltip select badge
```

This copies component files into `src/components/ui/`. Each is a self-contained `.tsx` file using Radix primitives + Tailwind classes.

---

## 2. Directory Structure (Phase 4 Deliverables)

After this phase, the following files exist:

```
ui/frontend/
├── package.json
├── tsconfig.json
├── vite.config.ts
├── index.html
├── public/
│   └── favicon.svg
├── src/
│   ├── main.tsx                          # React root + providers
│   ├── App.tsx                           # Route definitions
│   ├── index.css                         # Tailwind v4 + theme
│   │
│   ├── api/
│   │   ├── client.ts                     # fetch wrapper with JWT
│   │   ├── auth.ts                       # login, refresh, me
│   │   └── alerts.ts                     # alert stats (for dashboard)
│   │
│   ├── hooks/
│   │   ├── useAuth.ts                    # TanStack Query auth hooks
│   │   └── useAlerts.ts                  # useAlertStats hook
│   │
│   ├── stores/
│   │   └── auth.ts                       # Zustand: token, user, roles
│   │
│   ├── components/
│   │   ├── ui/                           # shadcn/ui primitives (auto-generated)
│   │   │   ├── button.tsx
│   │   │   ├── card.tsx
│   │   │   ├── input.tsx
│   │   │   ├── label.tsx
│   │   │   ├── separator.tsx
│   │   │   ├── avatar.tsx
│   │   │   ├── dropdown-menu.tsx
│   │   │   ├── dialog.tsx
│   │   │   ├── tooltip.tsx
│   │   │   ├── select.tsx
│   │   │   └── badge.tsx
│   │   ├── layout/
│   │   │   ├── AppShell.tsx              # sidebar + header + <Outlet />
│   │   │   ├── Sidebar.tsx               # nav links, role-aware
│   │   │   └── Header.tsx                # user menu, logout
│   │   └── dashboard/
│   │       ├── StatCard.tsx              # single metric card
│   │       ├── AlertsBySeverity.tsx      # bar/pie chart
│   │       ├── AlertsByChannel.tsx       # bar chart
│   │       └── AlertsOverTime.tsx        # line/area chart
│   │
│   ├── pages/
│   │   ├── LoginPage.tsx                 # login form
│   │   ├── DashboardPage.tsx             # overview metrics
│   │   └── NotFoundPage.tsx              # 404
│   │
│   └── lib/
│       ├── types.ts                      # TypeScript types (mirror backend schemas)
│       ├── constants.ts                  # severity, channel, status enums
│       └── utils.ts                      # cn(), date formatting, role checks
│
└── tests/
    ├── setup.ts                          # vitest setup (jest-dom matchers)
    ├── LoginPage.test.tsx                # login form tests
    └── Dashboard.test.tsx                # dashboard rendering tests
```

---

## 3. TypeScript Types (`src/lib/types.ts`)

Mirror the backend Pydantic schemas exactly. These are the contracts the frontend relies on.

```typescript
// ── Auth ──────────────────────────────────────────────

export interface LoginRequest {
  username: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
}

export interface UserProfile {
  id: string;           // UUID
  username: string;
  email: string;
  is_active: boolean;
  roles: string[];      // ["reviewer", "supervisor", "admin"]
  created_at: string;   // ISO datetime
  updated_at: string;
}

// ── Pagination ────────────────────────────────────────

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  offset: number;
  limit: number;
}

// ── Alerts ────────────────────────────────────────────

export type Severity = "low" | "medium" | "high" | "critical";
export type AlertStatus = "open" | "in_review" | "closed";

export interface AlertOut {
  id: string;
  name: string;
  rule_id: string;
  rule_name?: string;
  policy_name?: string;
  es_index: string;
  es_document_id: string;
  es_document_ts?: string;
  severity: Severity;
  status: AlertStatus;
  created_at: string;
}

export interface AlertWithMessage extends AlertOut {
  message?: ESMessage;
}

// ── Alert Stats (Dashboard) ───────────────────────────

export interface BucketCount {
  key: string;
  count: number;
}

export interface TimeSeriesPoint {
  date: string;
  count: number;
}

export interface AlertStats {
  by_severity: BucketCount[];
  by_channel: BucketCount[];
  by_status: BucketCount[];
  over_time: TimeSeriesPoint[];
  total: number;
}

// ── Messages (ES) ─────────────────────────────────────

export interface Participant {
  id: string;
  name: string;
  role: string;
}

export interface Attachment {
  name: string;
  content_type: string;
  s3_uri: string;
}

export interface Entity {
  text: string;
  label: string;
  start?: number;
  end?: number;
}

export interface ESMessage {
  message_id: string;
  channel: string;
  direction?: string;
  timestamp: string;
  participants: Participant[];
  body_text?: string;
  audio_ref?: string;
  attachments: Attachment[];
  transcript?: string;
  language?: string;
  translated_text?: string;
  entities: Entity[];
  sentiment?: string;
  sentiment_score?: number;
  risk_score?: number;
  matched_policies: string[];
  processing_status?: string;
}

// ── Decisions ─────────────────────────────────────────

export interface DecisionStatusOut {
  id: string;
  name: string;
  description?: string;
  is_terminal: boolean;
}

export interface DecisionOut {
  id: string;
  alert_id: string;
  reviewer_id: string;
  status_id: string;
  status_name?: string;
  comment?: string;
  decided_at: string;
}

// ── Queues ────────────────────────────────────────────

export type BatchStatus = "pending" | "in_progress" | "completed";

export interface QueueOut {
  id: string;
  name: string;
  description?: string;
  policy_id: string;
  created_by?: string;
  created_at: string;
  updated_at: string;
}

export interface QueueDetail extends QueueOut {
  batch_count: number;
  total_items: number;
}

export interface BatchOut {
  id: string;
  queue_id: string;
  name?: string;
  assigned_to?: string;
  assigned_by?: string;
  assigned_at?: string;
  status: BatchStatus;
  created_at: string;
  updated_at: string;
  item_count: number;
}

// ── Users / Groups ────────────────────────────────────

export interface UserOut {
  id: string;
  username: string;
  email: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface GroupOut {
  id: string;
  name: string;
  description?: string;
  created_at: string;
  updated_at: string;
}

export interface RoleOut {
  id: string;
  name: string;
  description?: string;
}

// ── Policy ────────────────────────────────────────────

export interface RiskModelOut {
  id: string;
  name: string;
  description?: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface PolicyOut {
  id: string;
  risk_model_id: string;
  name: string;
  description?: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface RuleOut {
  id: string;
  policy_id: string;
  name: string;
  description?: string;
  kql: string;
  severity: Severity;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// ── Audit ─────────────────────────────────────────────

export interface AuditLogEntry {
  id: string;
  decision_id: string;
  actor_id: string;
  action: string;
  old_values?: Record<string, unknown>;
  new_values?: Record<string, unknown>;
  created_at: string;
}
```

---

## 4. Constants (`src/lib/constants.ts`)

```typescript
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
```

---

## 5. Utility Functions (`src/lib/utils.ts`)

```typescript
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import { ROLE_HIERARCHY } from "./constants";

/** shadcn/ui class merge helper */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Check if user has at least the given role level */
export function hasRole(userRoles: string[], requiredRole: string): boolean {
  const requiredLevel = ROLE_HIERARCHY[requiredRole] ?? 0;
  return userRoles.some((r) => (ROLE_HIERARCHY[r] ?? 0) >= requiredLevel);
}

/** Format ISO datetime for display */
export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Format relative time (e.g., "2 hours ago") */
export function formatRelative(iso: string): string {
  const seconds = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  const intervals: [number, string][] = [
    [86400, "day"],
    [3600, "hour"],
    [60, "minute"],
  ];
  for (const [secs, label] of intervals) {
    const count = Math.floor(seconds / secs);
    if (count >= 1) return `${count} ${label}${count > 1 ? "s" : ""} ago`;
  }
  return "just now";
}
```

---

## 6. API Client Layer

### 6.1 `src/api/client.ts` — Fetch Wrapper with JWT

```typescript
import { useAuthStore } from "@/stores/auth";

const BASE_URL = "/api/v1";

export class ApiError extends Error {
  constructor(
    public status: number,
    public body: unknown,
  ) {
    super(`API error ${status}`);
    this.name = "ApiError";
  }
}

async function refreshAccessToken(): Promise<string | null> {
  const { refreshToken, setTokens, logout } = useAuthStore.getState();
  if (!refreshToken) return null;

  try {
    const res = await fetch(`${BASE_URL}/auth/refresh`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${refreshToken}`,
      },
    });
    if (!res.ok) {
      logout();
      return null;
    }
    const data = await res.json();
    setTokens(data.access_token, data.refresh_token);
    return data.access_token;
  } catch {
    logout();
    return null;
  }
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const { accessToken } = useAuthStore.getState();

  const headers = new Headers(options.headers);
  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }
  if (!headers.has("Content-Type") && options.body) {
    headers.set("Content-Type", "application/json");
  }

  let res = await fetch(`${BASE_URL}${path}`, { ...options, headers });

  // Auto-refresh on 401
  if (res.status === 401 && accessToken) {
    const newToken = await refreshAccessToken();
    if (newToken) {
      headers.set("Authorization", `Bearer ${newToken}`);
      res = await fetch(`${BASE_URL}${path}`, { ...options, headers });
    }
  }

  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new ApiError(res.status, body);
  }

  // Handle 204 No Content
  if (res.status === 204) return undefined as T;

  return res.json();
}
```

**Design notes:**
- Reads token from Zustand store (not localStorage — tokens live in memory only)
- Automatic 401 → refresh → retry (one retry)
- On refresh failure, calls `logout()` which clears state and redirects to `/login`
- Throws typed `ApiError` for downstream error handling
- No external dependencies (uses native `fetch`)

### 6.2 `src/api/auth.ts`

```typescript
import { apiFetch } from "./client";
import type { LoginRequest, TokenResponse, UserProfile } from "@/lib/types";

export async function login(credentials: LoginRequest): Promise<TokenResponse> {
  return apiFetch<TokenResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify(credentials),
  });
}

export async function refreshToken(): Promise<TokenResponse> {
  return apiFetch<TokenResponse>("/auth/refresh", {
    method: "POST",
  });
}

export async function getMe(): Promise<UserProfile> {
  return apiFetch<UserProfile>("/auth/me");
}
```

### 6.3 `src/api/alerts.ts` (stats only — full alert API comes in Phase 5)

```typescript
import { apiFetch } from "./client";
import type { AlertStats } from "@/lib/types";

export async function getAlertStats(): Promise<AlertStats> {
  return apiFetch<AlertStats>("/alerts/stats");
}
```

---

## 7. Zustand Auth Store (`src/stores/auth.ts`)

```typescript
import { create } from "zustand";
import type { UserProfile } from "@/lib/types";

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  user: UserProfile | null;
  isAuthenticated: boolean;

  setTokens: (access: string, refresh: string) => void;
  setUser: (user: UserProfile) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  accessToken: null,
  refreshToken: null,
  user: null,
  isAuthenticated: false,

  setTokens: (access, refresh) =>
    set({ accessToken: access, refreshToken: refresh, isAuthenticated: true }),

  setUser: (user) => set({ user }),

  logout: () =>
    set({
      accessToken: null,
      refreshToken: null,
      user: null,
      isAuthenticated: false,
    }),
}));
```

**Design notes:**
- Tokens live in memory only (not localStorage) — on page refresh the session is lost and the user must re-login. This is the more secure approach; persisted sessions can be added later via httpOnly refresh cookie.
- `isAuthenticated` is derived from whether `accessToken` is set.
- The store is accessed both by React components (via hook) and by the API client (via `useAuthStore.getState()`).

---

## 8. TanStack Query Hooks

### 8.1 `src/hooks/useAuth.ts`

```typescript
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router";
import { login, getMe } from "@/api/auth";
import { useAuthStore } from "@/stores/auth";
import type { LoginRequest } from "@/lib/types";

export function useLogin() {
  const { setTokens, setUser } = useAuthStore();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (credentials: LoginRequest) => login(credentials),
    onSuccess: async (data) => {
      setTokens(data.access_token, data.refresh_token);
      // Fetch user profile immediately after login
      const user = await getMe();
      setUser(user);
      queryClient.setQueryData(["auth", "me"], user);
      navigate("/");
    },
  });
}

export function useCurrentUser() {
  const { isAuthenticated, setUser } = useAuthStore();

  return useQuery({
    queryKey: ["auth", "me"],
    queryFn: async () => {
      const user = await getMe();
      setUser(user);
      return user;
    },
    enabled: isAuthenticated,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

export function useLogout() {
  const { logout } = useAuthStore();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  return () => {
    logout();
    queryClient.clear();
    navigate("/login");
  };
}
```

### 8.2 `src/hooks/useAlerts.ts` (stats only for dashboard)

```typescript
import { useQuery } from "@tanstack/react-query";
import { getAlertStats } from "@/api/alerts";

export function useAlertStats() {
  return useQuery({
    queryKey: ["alerts", "stats"],
    queryFn: getAlertStats,
    refetchInterval: 60_000, // auto-refresh every 60 seconds
  });
}
```

---

## 9. App Entry Point & Routing

### 9.1 `src/main.tsx`

```typescript
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { App } from "./App";
import "./index.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 30_000,     // 30 seconds
    },
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <QueryClientProvider client={queryClient}>
        <App />
        <ReactQueryDevtools initialIsOpen={false} />
      </QueryClientProvider>
    </BrowserRouter>
  </StrictMode>,
);
```

### 9.2 `src/App.tsx`

```typescript
import { Routes, Route, Navigate, Outlet } from "react-router";
import { useAuthStore } from "@/stores/auth";
import { AppShell } from "@/components/layout/AppShell";
import { LoginPage } from "@/pages/LoginPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { NotFoundPage } from "@/pages/NotFoundPage";

/** Redirects to /login if not authenticated */
function RequireAuth() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <Outlet />;
}

/** Redirects to / if already authenticated */
function GuestOnly() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  if (isAuthenticated) return <Navigate to="/" replace />;
  return <Outlet />;
}

export function App() {
  return (
    <Routes>
      {/* Public routes */}
      <Route element={<GuestOnly />}>
        <Route path="/login" element={<LoginPage />} />
      </Route>

      {/* Authenticated routes — wrapped in AppShell */}
      <Route element={<RequireAuth />}>
        <Route element={<AppShell />}>
          <Route index element={<DashboardPage />} />

          {/* Placeholder routes for Phase 5+ pages */}
          <Route path="/alerts" element={<ComingSoon label="Alerts" />} />
          <Route path="/alerts/:id" element={<ComingSoon label="Alert Detail" />} />
          <Route path="/messages" element={<ComingSoon label="Messages" />} />
          <Route path="/queues" element={<ComingSoon label="Queues" />} />
          <Route path="/policies" element={<ComingSoon label="Policies" />} />
          <Route path="/admin" element={<ComingSoon label="Admin" />} />
          <Route path="/audit" element={<ComingSoon label="Audit Log" />} />
        </Route>
      </Route>

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}

/** Temporary placeholder for routes not yet implemented */
function ComingSoon({ label }: { label: string }) {
  return (
    <div className="flex items-center justify-center h-full">
      <p className="text-muted-foreground text-lg">{label} — coming in Phase 5</p>
    </div>
  );
}
```

**Routing design:**
- `RequireAuth` layout route — checks Zustand `isAuthenticated`, redirects to `/login` if not
- `GuestOnly` layout route — prevents authenticated users from seeing the login page
- `AppShell` layout route — renders sidebar + header + `<Outlet />` for nested pages
- All Phase 5+ routes are stubbed with `ComingSoon` so the sidebar links work immediately

---

## 10. Layout Components

### 10.1 `AppShell.tsx`

The top-level authenticated layout. Renders the sidebar, header, and page content.

```
┌─────────────────────────────────────────────────────────┐
│ ┌──────────┐ ┌────────────────────────────────────────┐ │
│ │          │ │  Header (user menu, notifications)     │ │
│ │          │ ├────────────────────────────────────────┤ │
│ │ Sidebar  │ │                                        │ │
│ │          │ │  <Outlet /> (page content)              │ │
│ │          │ │                                        │ │
│ │          │ │                                        │ │
│ └──────────┘ └────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

```typescript
import { Outlet } from "react-router";
import { Sidebar } from "./Sidebar";
import { Header } from "./Header";

export function AppShell() {
  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <Header />
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
```

### 10.2 `Sidebar.tsx`

Role-aware navigation. Admin-only links are hidden from reviewers/supervisors.

```typescript
import { NavLink } from "react-router";
import {
  LayoutDashboard,
  AlertTriangle,
  Search,
  ListTodo,
  Shield,
  Users,
  FileText,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { hasRole } from "@/lib/utils";
import { useAuthStore } from "@/stores/auth";
import { Separator } from "@/components/ui/separator";

interface NavItem {
  to: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  minRole: string;
}

const NAV_ITEMS: NavItem[] = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, minRole: "reviewer" },
  { to: "/alerts", label: "Alerts", icon: AlertTriangle, minRole: "reviewer" },
  { to: "/messages", label: "Messages", icon: Search, minRole: "reviewer" },
  { to: "/queues", label: "Queues", icon: ListTodo, minRole: "reviewer" },
  { to: "/policies", label: "Policies", icon: Shield, minRole: "admin" },
  { to: "/admin", label: "Users & Groups", icon: Users, minRole: "admin" },
  { to: "/audit", label: "Audit Log", icon: FileText, minRole: "supervisor" },
];

export function Sidebar() {
  const roles = useAuthStore((s) => s.user?.roles ?? []);

  const visibleItems = NAV_ITEMS.filter((item) =>
    hasRole(roles, item.minRole),
  );

  return (
    <aside className="flex w-64 flex-col border-r bg-card">
      {/* Brand */}
      <div className="flex h-14 items-center gap-2 px-4 font-semibold">
        <Shield className="h-6 w-6 text-brand-600" />
        <span className="text-lg">Umbrella</span>
      </div>

      <Separator />

      {/* Navigation */}
      <nav className="flex-1 space-y-1 p-2">
        {visibleItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
              )
            }
          >
            <item.icon className="h-4 w-4" />
            {item.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
```

### 10.3 `Header.tsx`

Top bar with user avatar, role badge, and logout.

```typescript
import { useAuthStore } from "@/stores/auth";
import { useLogout } from "@/hooks/useAuth";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { LogOut, User as UserIcon } from "lucide-react";

export function Header() {
  const user = useAuthStore((s) => s.user);
  const logout = useLogout();

  const initials = user?.username
    ?.split(/[._-]/)
    .map((s) => s[0]?.toUpperCase())
    .join("")
    .slice(0, 2) ?? "?";

  const primaryRole = user?.roles?.[0] ?? "viewer";

  return (
    <header className="flex h-14 items-center justify-between border-b bg-card px-6">
      <div /> {/* Left side — breadcrumbs or search (Phase 5+) */}

      <DropdownMenu>
        <DropdownMenuTrigger className="flex items-center gap-2 outline-none">
          <Badge variant="secondary" className="text-xs capitalize">
            {primaryRole}
          </Badge>
          <Avatar className="h-8 w-8">
            <AvatarFallback className="text-xs">{initials}</AvatarFallback>
          </Avatar>
        </DropdownMenuTrigger>

        <DropdownMenuContent align="end" className="w-48">
          <div className="px-2 py-1.5">
            <p className="text-sm font-medium">{user?.username}</p>
            <p className="text-xs text-muted-foreground">{user?.email}</p>
          </div>
          <DropdownMenuSeparator />
          <DropdownMenuItem>
            <UserIcon className="mr-2 h-4 w-4" />
            Profile
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={logout} className="text-destructive">
            <LogOut className="mr-2 h-4 w-4" />
            Logout
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </header>
  );
}
```

---

## 11. Login Page (`src/pages/LoginPage.tsx`)

Full-screen centered login form with React Hook Form + Zod validation.

```typescript
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

type LoginFormValues = z.infer<typeof loginSchema>;

export function LoginPage() {
  const loginMutation = useLogin();
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
  });

  const onSubmit = (data: LoginFormValues) => {
    loginMutation.mutate(data);
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted">
      <Card className="w-full max-w-sm">
        <CardHeader className="text-center">
          <div className="mx-auto mb-2 flex h-12 w-12 items-center justify-center rounded-full bg-brand-100">
            <Shield className="h-6 w-6 text-brand-600" />
          </div>
          <CardTitle className="text-xl">Umbrella</CardTitle>
          <p className="text-sm text-muted-foreground">
            Communications Monitoring
          </p>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="username">Username</Label>
              <Input
                id="username"
                autoComplete="username"
                autoFocus
                {...register("username")}
              />
              {errors.username && (
                <p className="text-sm text-destructive">
                  {errors.username.message}
                </p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                {...register("password")}
              />
              {errors.password && (
                <p className="text-sm text-destructive">
                  {errors.password.message}
                </p>
              )}
            </div>

            {loginMutation.isError && (
              <p className="text-sm text-destructive">
                Invalid username or password
              </p>
            )}

            <Button
              type="submit"
              className="w-full"
              disabled={loginMutation.isPending}
            >
              {loginMutation.isPending ? "Signing in..." : "Sign in"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
```

---

## 12. Dashboard Page (`src/pages/DashboardPage.tsx`)

Fetches `/alerts/stats` and renders four sections:
1. **Stat cards** — total alerts, count by severity
2. **Alerts over time** — area chart (Recharts)
3. **Alerts by severity** — bar chart
4. **Alerts by channel** — bar chart

### 12.1 `DashboardPage.tsx`

```typescript
import { useAlertStats } from "@/hooks/useAlerts";
import { StatCard } from "@/components/dashboard/StatCard";
import { AlertsBySeverity } from "@/components/dashboard/AlertsBySeverity";
import { AlertsByChannel } from "@/components/dashboard/AlertsByChannel";
import { AlertsOverTime } from "@/components/dashboard/AlertsOverTime";
import { AlertTriangle, AlertCircle, ShieldAlert, Info } from "lucide-react";

export function DashboardPage() {
  const { data: stats, isLoading, isError } = useAlertStats();

  if (isLoading) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div
              key={i}
              className="h-28 animate-pulse rounded-lg bg-muted"
            />
          ))}
        </div>
      </div>
    );
  }

  if (isError || !stats) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <p className="text-destructive">Failed to load dashboard data.</p>
      </div>
    );
  }

  const severityCount = (level: string) =>
    stats.by_severity.find((b) => b.key === level)?.count ?? 0;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Dashboard</h1>

      {/* Stat cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Total Alerts"
          value={stats.total}
          icon={AlertTriangle}
        />
        <StatCard
          title="Critical"
          value={severityCount("critical")}
          icon={ShieldAlert}
          variant="critical"
        />
        <StatCard
          title="High"
          value={severityCount("high")}
          icon={AlertCircle}
          variant="high"
        />
        <StatCard
          title="Medium / Low"
          value={severityCount("medium") + severityCount("low")}
          icon={Info}
          variant="medium"
        />
      </div>

      {/* Charts */}
      <div className="grid gap-6 lg:grid-cols-2">
        <AlertsOverTime data={stats.over_time} />
        <AlertsBySeverity data={stats.by_severity} />
      </div>

      <AlertsByChannel data={stats.by_channel} />
    </div>
  );
}
```

### 12.2 `StatCard.tsx`

```typescript
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { LucideIcon } from "lucide-react";

interface StatCardProps {
  title: string;
  value: number;
  icon: LucideIcon;
  variant?: "default" | "critical" | "high" | "medium";
}

const VARIANT_STYLES: Record<string, string> = {
  default: "text-foreground",
  critical: "text-severity-critical",
  high: "text-severity-high",
  medium: "text-severity-medium",
};

export function StatCard({
  title,
  value,
  icon: Icon,
  variant = "default",
}: StatCardProps) {
  return (
    <Card>
      <CardContent className="flex items-center gap-4 p-4">
        <div
          className={cn(
            "flex h-10 w-10 items-center justify-center rounded-lg bg-muted",
            VARIANT_STYLES[variant],
          )}
        >
          <Icon className="h-5 w-5" />
        </div>
        <div>
          <p className="text-sm text-muted-foreground">{title}</p>
          <p className={cn("text-2xl font-bold", VARIANT_STYLES[variant])}>
            {value.toLocaleString()}
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
```

### 12.3 `AlertsOverTime.tsx`

```typescript
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { TimeSeriesPoint } from "@/lib/types";

interface Props {
  data: TimeSeriesPoint[];
}

export function AlertsOverTime({ data }: Props) {
  const formatted = data.map((d) => ({
    ...d,
    date: new Date(d.date).toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
    }),
  }));

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Alerts Over Time</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={280}>
          <AreaChart data={formatted}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
            <XAxis dataKey="date" className="text-xs" />
            <YAxis className="text-xs" />
            <Tooltip />
            <Area
              type="monotone"
              dataKey="count"
              stroke="oklch(0.55 0.10 250)"
              fill="oklch(0.55 0.10 250 / 0.2)"
            />
          </AreaChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
```

### 12.4 `AlertsBySeverity.tsx`

```typescript
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { BucketCount } from "@/lib/types";

interface Props {
  data: BucketCount[];
}

const SEVERITY_BAR_COLORS: Record<string, string> = {
  critical: "oklch(0.55 0.22 25)",
  high: "oklch(0.65 0.20 40)",
  medium: "oklch(0.75 0.15 80)",
  low: "oklch(0.70 0.12 145)",
};

export function AlertsBySeverity({ data }: Props) {
  // Sort critical → low
  const sorted = [...data].sort((a, b) => {
    const order = ["critical", "high", "medium", "low"];
    return order.indexOf(a.key) - order.indexOf(b.key);
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Alerts by Severity</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={sorted}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
            <XAxis dataKey="key" className="text-xs capitalize" />
            <YAxis className="text-xs" />
            <Tooltip />
            <Bar dataKey="count" radius={[4, 4, 0, 0]}>
              {sorted.map((entry) => (
                <Cell
                  key={entry.key}
                  fill={SEVERITY_BAR_COLORS[entry.key] ?? "#888"}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
```

### 12.5 `AlertsByChannel.tsx`

```typescript
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { BucketCount } from "@/lib/types";

interface Props {
  data: BucketCount[];
}

export function AlertsByChannel({ data }: Props) {
  const formatted = data.map((d) => ({
    ...d,
    label: d.key.replace(/_/g, " "),
  }));

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Alerts by Channel</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={formatted} layout="vertical">
            <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
            <XAxis type="number" className="text-xs" />
            <YAxis
              type="category"
              dataKey="label"
              width={120}
              className="text-xs capitalize"
            />
            <Tooltip />
            <Bar
              dataKey="count"
              fill="oklch(0.55 0.10 250)"
              radius={[0, 4, 4, 0]}
            />
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
```

---

## 13. 404 Page (`src/pages/NotFoundPage.tsx`)

```typescript
import { Link } from "react-router";
import { Button } from "@/components/ui/button";

export function NotFoundPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4">
      <h1 className="text-6xl font-bold text-muted-foreground">404</h1>
      <p className="text-muted-foreground">Page not found</p>
      <Button asChild variant="outline">
        <Link to="/">Back to Dashboard</Link>
      </Button>
    </div>
  );
}
```

---

## 14. Test Setup

### 14.1 `tests/setup.ts`

```typescript
import "@testing-library/jest-dom/vitest";
```

### 14.2 `tests/LoginPage.test.tsx`

```typescript
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { LoginPage } from "@/pages/LoginPage";
import { describe, it, expect } from "vitest";

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>{ui}</BrowserRouter>
    </QueryClientProvider>,
  );
}

describe("LoginPage", () => {
  it("renders the login form", () => {
    renderWithProviders(<LoginPage />);
    expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /sign in/i })).toBeInTheDocument();
  });

  it("shows validation errors on empty submit", async () => {
    renderWithProviders(<LoginPage />);
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
    expect(await screen.findByText(/username is required/i)).toBeInTheDocument();
    expect(await screen.findByText(/password is required/i)).toBeInTheDocument();
  });
});
```

### 14.3 `tests/Dashboard.test.tsx`

```typescript
import { render, screen } from "@testing-library/react";
import { BrowserRouter } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { DashboardPage } from "@/pages/DashboardPage";
import { describe, it, expect, vi } from "vitest";

// Mock the hook
vi.mock("@/hooks/useAlerts", () => ({
  useAlertStats: () => ({
    data: {
      total: 42,
      by_severity: [
        { key: "critical", count: 5 },
        { key: "high", count: 12 },
        { key: "medium", count: 15 },
        { key: "low", count: 10 },
      ],
      by_channel: [
        { key: "email", count: 20 },
        { key: "teams_chat", count: 12 },
        { key: "bloomberg_chat", count: 10 },
      ],
      by_status: [
        { key: "open", count: 30 },
        { key: "in_review", count: 7 },
        { key: "closed", count: 5 },
      ],
      over_time: [
        { date: "2026-02-10", count: 8 },
        { date: "2026-02-11", count: 12 },
        { date: "2026-02-12", count: 10 },
      ],
    },
    isLoading: false,
    isError: false,
  }),
}));

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>{ui}</BrowserRouter>
    </QueryClientProvider>,
  );
}

describe("DashboardPage", () => {
  it("renders stat cards with data", () => {
    renderWithProviders(<DashboardPage />);
    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();  // critical
    expect(screen.getByText("12")).toBeInTheDocument(); // high
    expect(screen.getByText("25")).toBeInTheDocument(); // medium + low
  });

  it("renders chart titles", () => {
    renderWithProviders(<DashboardPage />);
    expect(screen.getByText("Alerts Over Time")).toBeInTheDocument();
    expect(screen.getByText("Alerts by Severity")).toBeInTheDocument();
    expect(screen.getByText("Alerts by Channel")).toBeInTheDocument();
  });
});
```

---

## 15. Implementation Order

Execute steps in this exact order. Each step is atomic and testable.

| Step | Task | Files Created/Modified | Verify |
|------|------|------------------------|--------|
| **1** | Initialize Vite project | `package.json`, `tsconfig.json`, `vite.config.ts`, `index.html` | `npm run dev` starts dev server |
| **2** | Install dependencies | `package-lock.json`, `node_modules/` | `npm install` succeeds |
| **3** | Set up Tailwind v4 | `src/index.css` | Tailwind classes render in browser |
| **4** | Initialize shadcn/ui | `components.json`, `src/components/ui/*`, `src/lib/utils.ts` | `npx shadcn@latest init` + add components |
| **5** | Create type definitions | `src/lib/types.ts`, `src/lib/constants.ts` | TypeScript compiles (`tsc --noEmit`) |
| **6** | Create auth store | `src/stores/auth.ts` | Import test in `tsc --noEmit` |
| **7** | Create API client | `src/api/client.ts`, `src/api/auth.ts`, `src/api/alerts.ts` | TypeScript compiles |
| **8** | Create hooks | `src/hooks/useAuth.ts`, `src/hooks/useAlerts.ts` | TypeScript compiles |
| **9** | Create main entry + App | `src/main.tsx`, `src/App.tsx` | App renders in browser (blank) |
| **10** | Create login page | `src/pages/LoginPage.tsx` | Navigate to `/login`, form renders |
| **11** | Create layout components | `src/components/layout/AppShell.tsx`, `Sidebar.tsx`, `Header.tsx` | After login, sidebar + header render |
| **12** | Create dashboard components | `src/components/dashboard/StatCard.tsx`, `AlertsBySeverity.tsx`, `AlertsByChannel.tsx`, `AlertsOverTime.tsx` | Components render with mock data |
| **13** | Create dashboard page | `src/pages/DashboardPage.tsx` | Dashboard shows live data from API |
| **14** | Create 404 page | `src/pages/NotFoundPage.tsx` | Navigate to `/nonexistent`, 404 renders |
| **15** | Set up tests | `tests/setup.ts`, `tests/LoginPage.test.tsx`, `tests/Dashboard.test.tsx` | `npm test` passes |
| **16** | Verify end-to-end | — | Login → dashboard → sidebar nav → logout |

---

## 16. Acceptance Criteria

Phase 4 is complete when:

- [ ] `npm run dev` starts the Vite dev server on port 5173
- [ ] `npm run build` produces a production bundle in `dist/` with no errors
- [ ] `npm test` runs Vitest and all tests pass
- [ ] `tsc --noEmit` reports zero type errors
- [ ] Navigating to `/login` shows the login form
- [ ] Submitting valid credentials calls `POST /api/v1/auth/login`, stores the JWT, and redirects to `/`
- [ ] Submitting invalid credentials shows an error message
- [ ] The dashboard at `/` shows 4 stat cards and 3 charts, all populated from `GET /api/v1/alerts/stats`
- [ ] The sidebar shows role-appropriate navigation links (admin sees all 7; reviewer sees 4)
- [ ] Clicking sidebar links navigates to the correct route (placeholder pages for Phase 5+)
- [ ] The header shows the username, role badge, and a working logout button
- [ ] Logging out clears the session and redirects to `/login`
- [ ] Visiting any authenticated route while logged out redirects to `/login`
- [ ] Visiting `/login` while logged in redirects to `/`
- [ ] Navigating to a non-existent route shows the 404 page
- [ ] Dashboard auto-refreshes alert stats every 60 seconds
- [ ] Token refresh works transparently when the access token expires (30-min window)

---

## 17. Non-Goals (Deferred to Later Phases)

These are explicitly **out of scope** for Phase 4:

- Alert table and detail page (Phase 5)
- Message search (Phase 6)
- Queue management UI (Phase 6)
- Policy/rule editor (Phase 6)
- User/group admin pages (Phase 6)
- Audit log page (Phase 6)
- Export functionality (Phase 6)
- Audio player component (Phase 6)
- Dark mode toggle (post-MVP)
- Responsive/mobile layout (Phase 7 polish)
- E2E testing with Playwright (Phase 7)
- Dockerfile and nginx config (Phase 7)
- K8s manifests for frontend (Phase 7)
- WebSocket real-time updates (post-MVP)
- SSO/OIDC login (post-MVP)
- Persistent sessions via httpOnly refresh cookie (post-MVP)
