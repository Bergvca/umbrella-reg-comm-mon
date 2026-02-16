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
  doc_count: number;
}

export interface TimeSeriesPoint {
  key_as_string: string;
  doc_count: number;
}

export interface AlertStats {
  by_severity: BucketCount[];
  by_channel: BucketCount[];
  by_status: BucketCount[];
  over_time: TimeSeriesPoint[];
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
  channel?: string;
  is_active: boolean;
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
  full_name?: string;
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
  actor_id: string | null;
  action: string;
  object_type?: string;
  object_id?: string;
  old_values: Record<string, unknown> | null;
  new_values: Record<string, unknown> | null;
  occurred_at: string;
  ip_address: string | null;
  user_agent: string | null;
}

// ── Queue Items ───────────────────────────────────────

export interface QueueItemOut {
  id: string;
  batch_id: string;
  alert_id: string;
  position: number;
  created_at: string;
}

// ── Message Search ─────────────────────────────────────

export interface ESMessageHit {
  message: ESMessage;
  index: string;
  score: number | null;
  highlights: Record<string, string[]>;
}

export interface MessageSearchResponse {
  hits: ESMessageHit[];
  total: number;
  offset: number;
  limit: number;
}

// ── Policy Detail ──────────────────────────────────────

export interface PolicyDetail extends PolicyOut {
  risk_model_name: string;
  rule_count: number;
  group_count: number;
}

export interface RiskModelDetail extends RiskModelOut {
  policy_count: number;
}

export interface GroupPolicyOut {
  group_id: string;
  group_name?: string;
  policy_id: string;
  assigned_by: string | null;
  assigned_at: string;
}

// ── Group Detail ───────────────────────────────────────

export interface GroupDetail extends GroupOut {
  roles: RoleOut[];
  member_count: number;
}

export type QueueBatch = BatchOut;

// ── User with Roles ────────────────────────────────────

export interface UserWithRoles extends UserOut {
  roles: string[];
}
