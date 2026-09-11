import type { AnalysisSummary } from "@/types/incidents";
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
