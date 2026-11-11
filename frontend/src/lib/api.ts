import type { ApiErrorBody } from "./types";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details: { field?: string; message: string }[] = [],
  ) {
    super(message);
  }
}

async function toError(res: Response): Promise<ApiError> {
  try {
    const body = (await res.json()) as ApiErrorBody;
    return new ApiError(res.status, body.error.code, body.error.message, body.error.details);
  } catch {
    return new ApiError(res.status, "http_error", `Request failed (${res.status}).`);
  }
}

/** Server-side fetch to the FastAPI backend (never cached: travel data is time-sensitive). */
export async function parseResponse<T>(res: Response): Promise<T> {
  if (!res.ok) throw await toError(res);
  return (await res.json()) as T;
}

function csrfToken(): string | undefined {
  if (typeof document === "undefined") return undefined;
  return document.cookie
    .split("; ")
    .find((c) => c.startsWith("tport_csrf="))
    ?.split("=")[1];
}

/** Browser-side fetch via the same-origin /api proxy, with CSRF header on mutations. */
export async function clientApi<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method ?? "GET").toUpperCase();
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (method !== "GET") {
    const token = csrfToken();
    if (token) headers.set("X-CSRF-Token", decodeURIComponent(token));
  }
  let res: Response;
  try {
    res = await fetch(path, { ...init, method, headers, credentials: "same-origin" });
  } catch {
    throw new ApiError(0, "network_error", "Network error. Check your connection.");
  }
  if (!res.ok) throw await toError(res);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}
