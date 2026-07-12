import { ApiError } from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const TOKEN_KEY = "oap_access_token";

let inMemoryToken: string | null = null;

export function getToken(): string | null {
  if (inMemoryToken !== null) return inMemoryToken;
  if (typeof window === "undefined") return null;
  inMemoryToken = window.localStorage.getItem(TOKEN_KEY);
  return inMemoryToken;
}

export function setToken(token: string | null) {
  inMemoryToken = token;
  if (typeof window === "undefined") return;
  if (token) {
    window.localStorage.setItem(TOKEN_KEY, token);
  } else {
    window.localStorage.removeItem(TOKEN_KEY);
  }
}

// Fired whenever a request comes back 401 so a single AuthProvider can
// react (clear state, redirect to /login) without every call site needing
// to know how to do that itself.
type UnauthorizedHandler = () => void;
let unauthorizedHandler: UnauthorizedHandler | null = null;
export function onUnauthorized(handler: UnauthorizedHandler) {
  unauthorizedHandler = handler;
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  form?: Record<string, string>;
  formData?: FormData;
  query?: Record<string, string | number | boolean | undefined>;
  skipAuth?: boolean;
}

function buildUrl(path: string, query?: RequestOptions["query"]) {
  const url = new URL(path.replace(/^\//, ""), API_BASE_URL + "/");
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined) url.searchParams.set(key, String(value));
    }
  }
  return url.toString();
}

async function extractErrorMessage(response: Response): Promise<string> {
  try {
    const data = await response.json();
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.detail)) {
      // FastAPI 422 validation errors: a list of {loc, msg, type}.
      return data.detail.map((d: { msg?: string }) => d.msg).filter(Boolean).join(", ") || response.statusText;
    }
    return response.statusText;
  } catch {
    return response.statusText || `Request failed (${response.status})`;
  }
}

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {};
  let body: BodyInit | undefined;

  if (options.formData) {
    body = options.formData;
    // Deliberately no Content-Type - the browser sets the multipart
    // boundary itself; setting it manually breaks the upload.
  } else if (options.form) {
    headers["Content-Type"] = "application/x-www-form-urlencoded";
    body = new URLSearchParams(options.form).toString();
  } else if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.body);
  }

  if (!options.skipAuth) {
    const token = getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(buildUrl(path, options.query), {
    method: options.method ?? "GET",
    headers,
    body,
  });

  if (response.status === 401 && !options.skipAuth) {
    unauthorizedHandler?.();
    throw new ApiError(401, "Your session has expired. Please log in again.");
  }

  if (!response.ok) {
    throw new ApiError(response.status, await extractErrorMessage(response));
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const contentType = response.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    return (await response.json()) as T;
  }
  return (await response.blob()) as unknown as T;
}

export { API_BASE_URL };
