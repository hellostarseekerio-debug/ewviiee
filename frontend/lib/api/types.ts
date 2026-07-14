// Mirrors app/api/schemas.py exactly - every field here corresponds to a
// real Pydantic model on the backend. Do not add fields that don't exist
// there; do not invent endpoints not present in app/api/routes/*.py.

export type UserRole = "admin" | "editor" | "reviewer" | "viewer";

export interface TokenResponse {
  access_token: string | null;
  token_type: string;
  mfa_required: boolean;
  pending_token: string | null;
  // Present on a successful login so the frontend can skip a second
  // round trip to GET /api/auth/me - optional (`?`) since an older
  // backend deploy predates this field (see the /posters crash
  // postmortem: never assume a field arrived just because the type says
  // so - fall back to fetching it separately when absent).
  user?: UserOut | null;
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

  total_posters: number;
  posters_by_district: Record<string, number>;
  posters_by_estate: Record<string, number>;
  posters_by_status: Record<string, number>;
  recent_poster_uploads: Array<{
    id: string;
    title: string | null;
    district: string | null;
    estate: string | null;
    created_at: string;
  }>;
  broken_dropbox_links: number;
  duplicate_poster_groups: number;
  downloads_today: number;
  pending_reviews: number;
  most_active_users: Array<{ actor: string | null; action_count: number }>;
  export_storage_bytes: number;
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
  | "needs_changes"
  | "approved"
  | "published"
  | "rejected"
  | "archived";

export interface PosterOut {
  id: string;
  district: string | null;
  region: string | null;
  estate: string | null;
  poster_title: string | null;
  poster_type: string | null;
  route_number: string | null;
  politicians: string[] | null;
  document_date: string | null;
  date_to: string | null;
  dropbox_url: string | null;
  language: string | null;
  keywords: string[] | null;
  notes: string | null;
  workflow_steps: WorkflowStep[] | null;
  approval_status: "pending" | "approved" | "rejected";
  status: PosterStatusValue;
  folder_id: string | null;
  campaign_name: string | null;
  government_department: string | null;
  version: string | null;
  source: string | null;
  needs_review: boolean;
  dropbox_link_broken: boolean | null;
  dropbox_last_verified_at: string | null;
  // Per-field confidence (0.0-1.0) / source ("regex" | "rule_engine" |
  // "ai" | "default") from the metadata extraction engine - optional
  // (`?`) since older backend deploys predate these two fields; a UI
  // reading them must not assume they're always present (see the
  // /posters crash postmortem - never index a field the API contract
  // says exists without checking it actually arrived on the wire).
  extraction_confidence?: Record<string, number> | null;
  extraction_sources?: Record<string, string> | null;
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
  folder_id?: string | null;
  campaign_name?: string | null;
  government_department?: string | null;
  version?: string | null;
}

export type PosterUpdateRequest = Partial<PosterCreateRequest> & {
  approval_status?: string | null;
  needs_review?: boolean | null;
};

export interface PosterBulkFieldUpdateRequest {
  ids: string[];
  district?: string | null;
  estate?: string | null;
  poster_type?: string | null;
  add_keywords?: string[] | null;
}

export interface PosterBulkStatusRequest {
  ids: string[];
  status: PosterStatusValue;
  force?: boolean;
}

export interface DuplicateGroupOut {
  reason: "exact_dropbox_link" | "similar_title";
  poster_ids: string[];
  detail: string;
}

export interface LinkVerifyResultOut {
  poster_id: string;
  dropbox_link_broken: boolean | null;
  dropbox_last_verified_at: string | null;
}

export interface PosterLinkHistoryOut {
  id: string;
  old_url: string | null;
  new_url: string | null;
  changed_by: string | null;
  changed_at: string;
}

export interface PosterBulkMoveRequest {
  ids: string[];
  folder_id: string | null;
}

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

// --- Folders: mirrors app/api/schemas.py's Folder* models - a generic,
// resource-agnostic system (app/folders/service.py), not poster-specific.

export interface FolderOut {
  id: string;
  name: string;
  parent_id: string | null;
  path: string;
  depth: number;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface FolderStatsOut {
  folder_id: string;
  direct_subfolders: number;
  direct_items: number;
  total_subfolders: number;
  total_items: number;
}

export interface FolderDetailOut {
  folder: FolderOut;
  breadcrumbs: FolderOut[];
  stats: FolderStatsOut;
  children: FolderOut[];
}

export interface FolderTreeNodeOut {
  id: string;
  name: string;
  parent_id: string | null;
  depth: number;
  direct_items: number;
  total_items: number;
  children: FolderTreeNodeOut[];
}

export interface FolderCreateRequest {
  name: string;
  parent_id?: string | null;
}

// --- Starred items (favorites) - reusable across resource types ----------

export interface StarredItemOut {
  id: string;
  resource_type: string;
  resource_id: string;
  created_at: string;
}

// --- ZIP export (app/storage/archive_zip.py) ------------------------------

export interface PosterZipExportRequest {
  ids?: string[] | null;
  folder_id?: string | null;
  recursive?: boolean;
  q?: string | null;
  district?: string | null;
  poster_type?: string | null;
  date_from?: string | null;
  date_to?: string | null;
  has_dropbox?: boolean | null;
}

export interface ExportJobOut {
  id: string;
  resource_type: string;
  status: "pending" | "running" | "completed" | "failed";
  requested_by: string | null;
  total_items: number;
  included_items: number;
  file_size_bytes: number | null;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface ZipExportAcceptedResponse {
  job_id: string;
  status: string;
  total_items: number;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}
