import { clearToken, getToken } from "@/lib/auth";
import { track } from "@/lib/telemetry";

function getBaseUrl(): string {
  const url = (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/$/, "");
  if (!url) {
    // H8: this used to throw at module import time. A module-level
    // throw fires during hydration, not at build time as the previous
    // comment claimed -- with no error boundary to catch it (see
    // app/error.tsx), that crashed the whole page with a blank screen
    // and no message. Throwing lazily, only when a request actually
    // needs the URL, lets the error boundary catch it and show a real
    // message instead.
    throw new Error("NEXT_PUBLIC_API_URL is not set. Check your .env.local.");
  }
  return url;
}

const API_LATENCY_SAMPLE_RATE = 0.1; // plan: 10% normally, 100% of 5xx
const TRACKED_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE"];

/** /inventory/products/12?x=1 -> /inventory/products/:id (route template, never raw URLs). */
function routeTemplate(path: string): string {
  return path
    .split("?")[0]
    .split("/")
    .map((seg) => (/^\d+$/.test(seg) || /^[0-9a-f]{8}-[0-9a-f-]{27,}$/i.test(seg) ? ":id" : seg))
    .join("/");
}

export function recordApiCall(path: string, method: string | undefined, status: number, durationMs: number): void {
  const verb = (method ?? "GET").toUpperCase();
  if (!TRACKED_METHODS.includes(verb)) return;
  const endpoint = routeTemplate(path);
  const serverError = status >= 500 && status <= 599;
  if (serverError || Math.random() < API_LATENCY_SAMPLE_RATE) {
    track("api_latency_recorded", { endpoint, method: verb, status_code: status, duration_ms: Math.round(durationMs), sampled: !serverError });
  }
  if (serverError) {
    track("api_request_failed", {
      endpoint,
      method: verb,
      status_code: status,
      error_class: status === 500 ? "unhandled_exception" : "dependency_unavailable",
      occurrence_count: 1,
    });
  }
}

interface ApiErrorBody {
  detail?: string | { msg?: string }[];
}

async function parseErrorDetail(res: Response): Promise<string> {
  try {
    const body = (await res.json()) as ApiErrorBody;
    if (Array.isArray(body?.detail)) {
      return body.detail.map((d) => d.msg).filter(Boolean).join(" ");
    }
    if (typeof body?.detail === "string") {
      return body.detail;
    }
  } catch {
    // response wasn't JSON; fall through
  }
  return res.statusText || `Request failed with status ${res.status}`;
}

/**
 * The one fetch wrapper used by every protected API call in this app.
 * Attaches the Bearer token when present, and on any 401 response
 * globally clears the token and redirects to /login -- callers never
 * need to handle that case themselves.
 */
export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const baseUrl = getBaseUrl();
  const token = getToken();
  const isFormData = init?.body instanceof FormData;

  const headers: HeadersInit = {
    ...(isFormData ? {} : { "Content-Type": "application/json" }),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...init?.headers,
  };

  let res: Response;
  const startedAt = performance.now();
  try {
    res = await fetch(`${baseUrl}${path}`, { ...init, headers });
  } catch {
    throw new Error("Could not reach the API. Is the server running?");
  }
  recordApiCall(path, init?.method, res.status, performance.now() - startedAt);

  if (res.status === 401) {
    if (token) {
      // We believed we had an active session (a token was attached),
      // but the server disagrees -- this is a real session-expiry
      // case. Clear it and force a re-login.
      clearToken();
      if (typeof window !== "undefined") {
        // A full navigation (not router.push) is intentional here:
        // this runs from plain utility code with no access to
        // useRouter, and a hard reload also guarantees any stale
        // in-memory app state from the expired session is discarded.
        // eslint-disable-next-line @next/next/no-location-assign-relative-destination
        window.location.href = "/login";
      }
      throw new Error("Session expired. Please log in again.");
    }
    // No token was ever attached -- e.g. a login attempt with the
    // wrong password, or forgot/reset-password. A 401 here is a
    // normal API-level failure, not a session expiring, so it should
    // surface as a regular error message instead.
    throw new Error(await parseErrorDetail(res));
  }

  if (!res.ok) {
    throw new Error(await parseErrorDetail(res));
  }

  if (res.status === 204) {
    return undefined as T;
  }

  // H3: the success path parsed the body with no guard, while the
  // error path (parseErrorDetail above) carefully guards its own
  // parse. A 2xx response carrying HTML (a proxy/gateway interstitial)
  // or an empty body threw a raw SyntaxError straight out of this
  // function, which every caller then rendered verbatim into its red
  // error box.
  try {
    return (await res.json()) as T;
  } catch {
    throw new Error("Received an unexpected response from the server.");
  }
}

export function apiBaseUrl(): string {
  return getBaseUrl();
}
