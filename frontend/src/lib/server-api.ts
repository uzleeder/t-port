import { cookies, headers } from "next/headers";
import { ApiError, parseResponse } from "./api";

/**
 * Server-side fetch to the FastAPI backend (Server Components only). Never cached: travel data is
 * time-sensitive. Forwards the visitor's X-Forwarded-For (set by the front proxy) so the API
 * rate-limits per visitor rather than per web server. Call only inside a Suspense boundary.
 */
export async function serverApi<T>(path: string, init?: RequestInit): Promise<T> {
  const base = process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8000";
  const [incoming, jar] = await Promise.all([headers(), cookies()]);
  const forwarded = incoming.get("x-forwarded-for");
  const outgoing = new Headers(init?.headers);
  if (forwarded) outgoing.set("x-forwarded-for", forwarded);
  // Only the session cookie is forwarded (so signed-in searches appear under "Recent searches").
  const session = jar.get("tport_session")?.value;
  if (session && /^[\w-]{20,128}$/.test(session)) outgoing.set("cookie", `tport_session=${session}`);
  let res: Response;
  try {
    res = await fetch(`${base}${path}`, { ...init, headers: outgoing, cache: "no-store" });
  } catch {
    throw new ApiError(503, "api_unreachable", "The T-Port service is unreachable. Try again shortly.");
  }
  return parseResponse<T>(res);
}
