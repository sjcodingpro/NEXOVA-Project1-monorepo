export interface AnalysisSummary {
  total: number;
  valid_count: number;
  invalid_count: number;
  invalid_rule_counts: Record<string, number>;
  category_counts: Record<string, number>;
  status_counts: Record<string, number>;
  closed_total: number;
  scored_total: number;
  score_distribution: Record<string, number>;
  avg_score: number;
}

export interface ApiErrorBody {
  detail: string;
}

// --- Centralized Incident Manager (CONTEXT.md) ------------------------------
// Distinct from AnalysisSummary above, which is the CSV-analyzer's raw
// TECHNICAL/BILLING/... + OPEN/CLOSED/DISCARDED values. These are the
// Incident Manager's own model values.

export type IncidentBranch = "central" | "valencia_operations" | "miami_office" | "remote";

export type IncidentCategory =
  | "technical_failure"
  | "process_error"
  | "client_complaint"
  | "candidate_issue"
  | "staff_issue"
  | "sla_breach"
  | "data_quality"
  | "other";

export type IncidentStatus = "open" | "in_progress" | "resolved" | "discarded";

export type IncidentOrigin = "customer" | "branch" | "internal";

export interface Incident {
  id: number;
  title: string;
  description: string;
  category: IncidentCategory;
  status: IncidentStatus;
  origin: IncidentOrigin;
  branch: IncidentBranch;
  created_at: string;
  updated_at: string;
}

export interface CreateIncidentPayload {
  title: string;
  description: string;
  category: IncidentCategory | "";
  origin: IncidentOrigin | "";
  branch: IncidentBranch | "";
}

export interface IncidentManagerSummary {
  by_status: Record<IncidentStatus, number>;
  by_category: Record<IncidentCategory, number>;
  by_origin: Record<IncidentOrigin, number>;
  by_branch: Record<IncidentBranch, number>;
}
