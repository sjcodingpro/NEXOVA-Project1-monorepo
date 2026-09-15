import type {
  AnalysisSummary,
  CreateIncidentPayload,
  Incident,
  IncidentBranch,
  IncidentCategory,
  IncidentManagerSummary,
  IncidentOrigin,
  IncidentStatus,
} from "@/types/incidents";
import { apiFetch, apiBaseUrl } from "@/lib/api-client";

export async function analyzeIncidents(file: File): Promise<AnalysisSummary> {
  const formData = new FormData();
  formData.append("file", file);

  return apiFetch<AnalysisSummary>("/api/incidents/analyze", {
    method: "POST",
    body: formData,
  });
}

/**
 * GET /api/incidents/results/export is intentionally left public
 * (not one of the 5 routes protected in AUTH-01), so this is a plain
 * URL for a direct browser download -- no token needed.
 */
export function exportResultsUrl(): string {
  return `${apiBaseUrl()}/api/incidents/results/export`;
}

// --- Centralized Incident Manager -------------------------------------------

export function listIncidents(filters?: {
  status?: IncidentStatus;
  origin?: IncidentOrigin;
  branch?: IncidentBranch;
  category?: IncidentCategory;
}): Promise<Incident[]> {
  const params = new URLSearchParams();
  if (filters?.status) params.set("status", filters.status);
  if (filters?.origin) params.set("origin", filters.origin);
  if (filters?.branch) params.set("branch", filters.branch);
  if (filters?.category) params.set("category", filters.category);
  const qs = params.toString();
  return apiFetch<Incident[]>(`/api/incidents${qs ? `?${qs}` : ""}`);
}

export function getIncident(id: number): Promise<Incident> {
  return apiFetch<Incident>(`/api/incidents/${id}`);
}

export function createIncident(payload: CreateIncidentPayload): Promise<Incident> {
  return apiFetch<Incident>("/api/incidents", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateIncidentStatus(id: number, status: IncidentStatus): Promise<Incident> {
  return apiFetch<Incident>(`/api/incidents/${id}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}

export function getIncidentSummary(): Promise<IncidentManagerSummary> {
  return apiFetch<IncidentManagerSummary>("/api/incidents/summary");
}
