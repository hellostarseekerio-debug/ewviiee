// Mirrors app/api/schemas.py exactly - every field here corresponds to a
// real Pydantic model on the backend. Do not add fields that don't exist
// there; do not invent endpoints not present in app/api/routes/*.py.

export type UserRole = "admin" | "editor" | "reviewer" | "viewer";

export interface TokenResponse {
  access_token: string | null;
  token_type: string;
  mfa_required: boolean;
  pending_token: string | null;
}

export interface UserOut {
  id: string;
  username: string;
  full_name: string | null;
  role: UserRole;
  is_active: boolean;
  mfa_enabled: boolean;
  created_at: string;
  last_login_at: string | null;
}

export interface UserUpdateRequest {
  full_name?: string | null;
  role?: UserRole | null;
  is_active?: boolean | null;
}

export interface UserCreateRequest {
  username: string;
  password: string;
  full_name?: string | null;
  role: UserRole;
}

export interface MFASetupResponse {
  secret: string;
  otpauth_uri: string;
  recovery_codes: string[];
}

export interface DocumentOut {
  id: string;
  filename: string;
  document_type: string | null;
  workflow_name: string | null;
  status: string;
  district: string | null;
  estate: string | null;
  title: string | null;
  politician: string | null;
  reference_number: string | null;
  document_date: string | null;
  language: string | null;
  version: string | null;
  ai_confidence: number | null;
  ocr_confidence: number | null;
  approval_status: "pending" | "approved" | "rejected";
  reviewed_by: string | null;
  reviewed_at: string | null;
  review_notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface DocumentVersionOut {
  id: string;
  version_number: number;
  file_path: string;
  checksum_sha256: string | null;
  created_by: string | null;
  notes: string | null;
  created_at: string;
}

export interface SearchResponse {
  total: number;
  results: DocumentOut[];
}

export interface PluginOut {
  plugin_id: string;
  display_name: string;
  version: string;
}

export interface WorkflowSummary {
  name: string;
  display_name: string;
  plugin: string;
  stages: string[];
}

export interface WorkflowRunRequest {
  workflow_name: string;
  document_paths: string[];
  triggered_by?: string | null;
}

export interface WorkflowRunResult {
  document_path: string;
  success: boolean;
  halt_reason: string | null;
  output_path: string | null;
  fields: Record<string, unknown>;
}

export interface WorkflowRunResponse {
  workflow_name: string;
  total: number;
  succeeded: number;
  failed: number;
  results: WorkflowRunResult[];
}

export interface DashboardStats {
  total_documents: number;
  documents_by_status: Record<string, number>;
  documents_by_approval_status: Record<string, number>;
  total_users: number;
  active_users: number;
  ai_usage_total: number;
  ai_usage_cloud: number;
  ai_usage_local: number;
  recent_activity: Array<{
    actor: string | null;
    action: string;
    resource_type: string | null;
    resource_id: string | null;
    success: boolean;
    created_at: string;
  }>;
}

export interface SystemSettings {
  [key: string]: string;
}

// --- Poster Archive: mirrors app/api/schemas.py's Poster* models exactly -
export interface WorkflowStep {
  step: number;
  action: string;
  detail?: string | null;
}

// Mirrors app.core.models.PosterStatus - see app/posters/status.py for the
// allowed-transition graph and role rules enforced server-side.
export type PosterStatusValue =
  | "draft"
  | "pending_review"
  | "approved"
  | "published"
  | "rejected"
  | "archived";

export interface PosterOut {
  id: string;
  district: string | null;
  estate: string | null;
  poster_title: string | null;
  poster_type: string | null;
  route_number: string | null;
  document_date: string | null;
  dropbox_url: string | null;
  language: string | null;
  keywords: string[] | null;
  notes: string | null;
  workflow_steps: WorkflowStep[] | null;
  approval_status: "pending" | "approved" | "rejected";
  status: PosterStatusValue;
  ai_summary: string | null;
  ocr_text: string | null;
  attachments: Record<string, unknown>[] | null;
  created_at: string;
  updated_at: string;
}

export interface PosterStatusChangeRequest {
  status: PosterStatusValue;
  notes?: string | null;
  force?: boolean;
}

export interface PosterListResponse {
  total: number;
  results: PosterOut[];
}

export interface PosterCreateRequest {
  district?: string | null;
  estate?: string | null;
  poster_title?: string | null;
  poster_type?: string | null;
  route_number?: string | null;
  document_date?: string | null;
  dropbox_url?: string | null;
  language?: string | null;
  keywords?: string[] | null;
  notes?: string | null;
  workflow_steps?: WorkflowStep[] | null;
}

export type PosterUpdateRequest = Partial<PosterCreateRequest> & { approval_status?: string | null };

export interface PosterImportResult {
  dropbox_url: string;
  status: "imported" | "duplicate" | "invalid_url";
  id?: string | null;
  reason?: string | null;
}

export interface PosterImportResponse {
  total_parsed: number;
  imported: number;
  duplicates: number;
  invalid: number;
  results: PosterImportResult[];
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}
