import { apiFetch, API_BASE_URL, getToken } from "./client";
import type {
  DashboardStats,
  DocumentOut,
  DocumentVersionOut,
  MFASetupResponse,
  PluginOut,
  PosterCreateRequest,
  PosterImportResponse,
  PosterListResponse,
  PosterOut,
  PosterUpdateRequest,
  SearchResponse,
  SystemSettings,
  TokenResponse,
  UserCreateRequest,
  UserOut,
  UserUpdateRequest,
  WorkflowRunRequest,
  WorkflowRunResponse,
  WorkflowSummary,
} from "./types";

// --- Auth: app/api/routes/auth.py ------------------------------------------
export const authApi = {
  login: (username: string, password: string) =>
    apiFetch<TokenResponse>("/api/auth/token", { method: "POST", form: { username, password }, skipAuth: true }),

  verifyMfa: (pending_token: string, code: string) =>
    apiFetch<TokenResponse>("/api/auth/mfa/verify", { method: "POST", body: { pending_token, code }, skipAuth: true }),

  me: () => apiFetch<UserOut>("/api/auth/me"),

  setupMfa: () => apiFetch<MFASetupResponse>("/api/auth/mfa/setup", { method: "POST" }),
  confirmMfa: (code: string) => apiFetch<{ mfa_enabled: boolean }>("/api/auth/mfa/confirm", { method: "POST", body: { code } }),
  disableMfa: (password: string) => apiFetch<{ mfa_enabled: boolean }>("/api/auth/mfa/disable", { method: "POST", body: { password } }),
  changePassword: (current_password: string, new_password: string) =>
    apiFetch<{ detail: string }>("/api/auth/change-password", { method: "POST", body: { current_password, new_password } }),

  listUsers: () => apiFetch<UserOut[]>("/api/auth/admin/users"),
  createUser: (payload: UserCreateRequest) =>
    apiFetch<{ id: string; username: string; role: string }>("/api/auth/admin/users", { method: "POST", body: payload }),
  updateUser: (username: string, payload: UserUpdateRequest) =>
    apiFetch<UserOut>(`/api/auth/admin/users/${encodeURIComponent(username)}`, { method: "PATCH", body: payload }),
  deactivateUser: (username: string) =>
    apiFetch<void>(`/api/auth/admin/users/${encodeURIComponent(username)}`, { method: "DELETE" }),
  resetPassword: (username: string, new_password: string) =>
    apiFetch<{ detail: string }>(`/api/auth/admin/users/${encodeURIComponent(username)}/reset-password`, {
      method: "POST",
      body: { new_password },
    }),
};

// --- Documents: app/api/routes/documents.py --------------------------------
export const documentsApi = {
  upload: (file: File, onProgress?: (pct: number) => void) => {
    const form = new FormData();
    form.append("file", file);
    return uploadWithProgress<{ stored_path: string; original_filename: string }>(
      "/api/documents/upload",
      form,
      onProgress
    );
  },
  get: (id: string) => apiFetch<DocumentOut>(`/api/documents/${id}`),
  list: (skip: number, limit: number) =>
    apiFetch<DocumentOut[]>("/api/documents", { query: { skip, limit } }),
  versions: (id: string) => apiFetch<DocumentVersionOut[]>(`/api/documents/${id}/versions`),
  approve: (id: string, notes?: string) =>
    apiFetch<DocumentOut>(`/api/documents/${id}/approve`, { method: "POST", body: { notes: notes ?? null } }),
  reject: (id: string, notes?: string) =>
    apiFetch<DocumentOut>(`/api/documents/${id}/reject`, { method: "POST", body: { notes: notes ?? null } }),
  remove: (id: string) => apiFetch<void>(`/api/documents/${id}`, { method: "DELETE" }),
  rollback: (id: string, version_id: string) =>
    apiFetch<DocumentOut>(`/api/documents/${id}/rollback`, { method: "POST", body: { version_id } }),
  downloadUrl: (id: string) => `${API_BASE_URL}/api/documents/${id}/download`,
};

// --- Search: app/api/routes/search.py --------------------------------------
export const searchApi = {
  search: (params: {
    keyword?: string;
    district?: string;
    estate?: string;
    workflow_name?: string;
    document_type?: string;
    politician?: string;
    reference_number?: string;
    filename?: string;
    date_from?: string;
    date_to?: string;
    limit?: number;
    offset?: number;
  }) => apiFetch<SearchResponse>("/api/search", { query: params }),
};

// --- Workflows: app/api/routes/workflows.py --------------------------------
export const workflowsApi = {
  list: () => apiFetch<WorkflowSummary[]>("/api/workflows"),
  run: (payload: WorkflowRunRequest) =>
    apiFetch<WorkflowRunResponse>("/api/workflows/run", { method: "POST", body: payload }),
};

// --- Plugins: app/api/routes/plugins.py ------------------------------------
export const pluginsApi = {
  list: () => apiFetch<PluginOut[]>("/api/plugins"),
};

// --- Settings: app/api/routes/settings.py -----------------------------------
export const settingsApi = {
  get: () => apiFetch<SystemSettings>("/api/settings"),
  update: (key: string, value: string) =>
    apiFetch<SystemSettings>("/api/settings", { method: "PUT", body: { key, value } }),
};

// --- Dashboard: app/api/routes/dashboard.py --------------------------------
export const dashboardApi = {
  stats: () => apiFetch<DashboardStats>("/api/dashboard/stats"),
};

// --- Health: app/api/main.py -------------------------------------------------
export const healthApi = {
  check: () => apiFetch<{ status: string; app: string }>("/health", { skipAuth: true }),
};

// --- Posters: app/api/routes/posters.py (Poster Archive) --------------------
export interface PosterFilters {
  district?: string;
  poster_type?: string;
  date_from?: string;
  date_to?: string;
  has_dropbox?: boolean;
}

export const postersApi = {
  import: (text: string) =>
    apiFetch<PosterImportResponse>("/api/posters/import", { method: "POST", body: { text } }),
  list: (params: PosterFilters & { skip?: number; limit?: number; sort_by?: string; sort_dir?: string }) =>
    apiFetch<PosterListResponse>("/api/posters", { query: params as Record<string, string | number | boolean | undefined> }),
  search: (params: PosterFilters & { q?: string; skip?: number; limit?: number }) =>
    apiFetch<PosterListResponse>("/api/posters/search", { query: params as Record<string, string | number | boolean | undefined> }),
  get: (id: string) => apiFetch<PosterOut>(`/api/posters/${id}`),
  create: (payload: PosterCreateRequest) => apiFetch<PosterOut>("/api/posters", { method: "POST", body: payload }),
  update: (id: string, payload: PosterUpdateRequest) =>
    apiFetch<PosterOut>(`/api/posters/${id}`, { method: "PATCH", body: payload }),
  remove: (id: string) => apiFetch<void>(`/api/posters/${id}`, { method: "DELETE" }),
  bulkDelete: (ids: string[]) =>
    apiFetch<{ deleted: number }>("/api/posters/bulk-delete", { method: "POST", body: { ids } }),
  exportCsvUrl: (filters: PosterFilters) => {
    const query = new URLSearchParams();
    for (const [key, value] of Object.entries(filters)) {
      if (value !== undefined) query.set(key, String(value));
    }
    return `${API_BASE_URL}/api/posters/export?${query.toString()}`;
  },
  downloadCsv: async (filters: PosterFilters) => {
    const response = await fetch(postersApi.exportCsvUrl(filters), {
      headers: { Authorization: `Bearer ${getToken()}` },
    });
    if (!response.ok) throw new Error("Export failed");
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "posters_export.csv";
    a.click();
    window.URL.revokeObjectURL(url);
  },
};

// XHR-based upload so we can report real progress - fetch() has no
// upload-progress event, which the "Upload progress" requirement needs.
function uploadWithProgress<T>(path: string, form: FormData, onProgress?: (pct: number) => void): Promise<T> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE_URL}${path}`);
    const token = typeof window !== "undefined" ? window.localStorage.getItem("oap_access_token") : null;
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && onProgress) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText));
        } catch {
          resolve(undefined as T);
        }
      } else {
        let message = xhr.statusText;
        try {
          const parsed = JSON.parse(xhr.responseText);
          if (typeof parsed.detail === "string") message = parsed.detail;
        } catch {
          /* fall through to statusText */
        }
        reject(new Error(message || `Upload failed (${xhr.status})`));
      }
    };
    xhr.onerror = () => reject(new Error("Network error during upload"));
    xhr.send(form);
  });
}
