/** Raw status values as returned by the Talent Tracker API. */
export type StatusValue = "received" | "in_progress" | "selected" | "discarded";

/** Raw stage values as returned by the Talent Tracker API. */
export type StageValue =
  | "pending"
  | "review"
  | "personal_interview"
  | "technical_interview"
  | "offer_presented";

export interface Note {
  id: string;
  record_id: string;
  content: string;
  created_at: string;
}

export interface Candidate {
  id: string;
  full_name: string;
  email: string;
  phone: string;
  position: string;
  linkedin_url: string | null;
  cv_url: string;
  status: StatusValue;
  stage: StageValue;
  experience_years: number;
  applied_at: string;
  updated_at: string;
  notes: Note[];
  notes_count: number;
}

/** GET /records response shape — paginated wrapper, not a bare array. */
export interface NotesListResponse {
  data: Note[];
  meta: { total: number };
}

export interface RecordsListResponse {
  total: number;
  page: number;
  limit: number;
  data: Candidate[];
}

/** Body for POST /records */
export interface CreateCandidatePayload {
  full_name: string;
  email: string;
  phone: string;
  position: string;
  linkedin_url: string | null;
  cv_url: string;
  experience_years: number;
}

/** Body for PUT /records/:id — full replace, same shape as create */
export type UpdateCandidatePayload = CreateCandidatePayload;

/** Body for PATCH /records/:id — status/stage only, both optional so either can be sent alone */
export interface PatchCandidatePayload {
  status?: StatusValue;
  stage?: StageValue;
}

/** Body for POST /records/:id/notes */
export interface CreateNotePayload {
  content: string;
}

/** Query params accepted by GET /records */
export interface RecordsQueryParams {
  status?: StatusValue;
  stage?: StageValue;
  search?: string;
  page?: number;
  limit?: number;
}
