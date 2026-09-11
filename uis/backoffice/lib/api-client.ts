import { clearToken, getToken } from "@/lib/auth";

const BASE_URL = (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/$/, "");

if (!BASE_URL) {
  throw new Error("NEXT_PUBLIC_API_URL is not set. Check your .env.local.");
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
  const token = getToken();
  const isFormData = init?.body instanceof FormData;

  const headers: HeadersInit = {
    ...(isFormData ? {} : { "Content-Type": "application/json" }),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...init?.headers,
  };

  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${path}`, { ...init, headers });
  } catch {
    throw new Error("Could not reach the API. Is the server running?");
  }

  if (res.status === 401) {
    clearToken();
    if (typeof window !== "undefined") {
      // A full navigation (not router.push) is intentional here: this
      // runs from plain utility code with no access to useRouter, and
      // a hard reload also guarantees any stale in-memory app state
      // from the expired session is discarded.
      // eslint-disable-next-line @next/next/no-location-assign-relative-destination
      window.location.href = "/login";
    }
    throw new Error("Session expired. Please log in again.");
  }

  if (!res.ok) {
    throw new Error(await parseErrorDetail(res));
  }

  if (res.status === 204) {
    return undefined as T;
  }

  return (await res.json()) as T;
}

export function apiBaseUrl(): string {
  return BASE_URL;
}
