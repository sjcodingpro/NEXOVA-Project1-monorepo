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

const BASE_URL = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "");

if (!BASE_URL) {
  // Fails loudly at build/dev time rather than producing confusing
  // "fetch failed" errors deep in a component.
  throw new Error("NEXT_PUBLIC_API_URL is not set. Check your .env.local.");
}

/**
 * Thin wrapper around fetch shared by every API call in the app.
 * Centralizes headers, base URL, and error handling so callers only
 * deal with typed request/response shapes.
 */
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${path}`, {
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

  return (await res.json()) as T;
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
