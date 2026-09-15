import type {
  Candidate,
  RecordsListResponse,
  RecordsQueryParams,
  CreateCandidatePayload,
  UpdateCandidatePayload,
  PatchCandidatePayload,
  Note,
  NotesListResponse,
  CreateNotePayload,
} from "@/types/candidate";

function getBaseUrl(): string {
  const url = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "");
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

/**
 * Thin wrapper around fetch shared by every API call in the app.
 * Centralizes headers, base URL, and error handling so callers only
 * deal with typed request/response shapes.
 */
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const baseUrl = getBaseUrl();
  let res: Response;
  try {
    res = await fetch(`${baseUrl}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...init?.headers,
      },
    });
  } catch {
    // Network failure (offline, DNS, CORS, etc.) — no response at all.
    throw new Error("Could not reach the server. Check your connection and try again.");
  }

  if (!res.ok) {
    let message = res.statusText || `Request failed with status ${res.status}`;
    try {
      const body = await res.json();
      // FastAPI validation errors come back as { detail: [{ msg, ... }] }
      if (Array.isArray(body?.detail)) {
        message = body.detail.map((d: { msg?: string }) => d.msg).filter(Boolean).join(" ");
      } else if (typeof body?.detail === "string") {
        message = body.detail;
      }
    } catch {
      // Response wasn't JSON — fall back to statusText already set above.
    }
    throw new Error(message);
  }

  if (res.status === 204) {
    return undefined as T;
  }

  // H3: the success path parsed the body with no guard, while the
  // error path just above carefully guards its own parse. A 2xx
  // response carrying HTML (a proxy/gateway interstitial) or an empty
  // body threw a raw SyntaxError straight out of this function, which
  // every caller then rendered verbatim.
  try {
    return (await res.json()) as T;
  } catch {
    throw new Error("Received an unexpected response from the server.");
  }
}

function buildQuery(params: RecordsQueryParams = {}): string {
  const search = new URLSearchParams();
  if (params.status) search.set("status", params.status);
  if (params.stage) search.set("stage", params.stage);
  if (params.search) search.set("search", params.search);
  if (params.page) search.set("page", String(params.page));
  if (params.limit) search.set("limit", String(params.limit));
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

export const api = {
  listCandidates(params?: RecordsQueryParams): Promise<RecordsListResponse> {
    return request<RecordsListResponse>(`/records${buildQuery(params)}`);
  },

  getCandidate(id: string): Promise<Candidate> {
    return request<Candidate>(`/records/${id}`);
  },

  createCandidate(payload: CreateCandidatePayload): Promise<Candidate> {
    return request<Candidate>("/records", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  updateCandidate(id: string, payload: UpdateCandidatePayload): Promise<Candidate> {
    return request<Candidate>(`/records/${id}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  },

  patchCandidate(id: string, payload: PatchCandidatePayload): Promise<Candidate> {
    return request<Candidate>(`/records/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },

  deleteCandidate(id: string): Promise<void> {
    return request<void>(`/records/${id}`, {
      method: "DELETE",
    });
  },

  listNotes(recordId: string): Promise<NotesListResponse> {
    return request<NotesListResponse>(`/records/${recordId}/notes`);
  },

  addNote(recordId: string, payload: CreateNotePayload): Promise<Note> {
    return request<Note>(`/records/${recordId}/notes`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  deleteNote(recordId: string, noteId: string): Promise<void> {
    return request<void>(`/records/${recordId}/notes/${noteId}`, {
      method: "DELETE",
    });
  },
};
