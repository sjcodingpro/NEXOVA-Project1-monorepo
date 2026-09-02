import type { AnalysisSummary, ApiErrorBody } from "@/types/incidents";

const BASE_URL = (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/$/, "");

if (!BASE_URL) {
  throw new Error("NEXT_PUBLIC_API_URL is not set. Check your .env.local.");
}

async function parseErrorDetail(res: Response): Promise<string> {
  try {
    const body = (await res.json()) as ApiErrorBody;
    if (body?.detail) return body.detail;
  } catch {
    // response wasn't JSON; fall through
  }
  return res.statusText || `Request failed with status ${res.status}`;
}

export async function analyzeIncidents(file: File): Promise<AnalysisSummary> {
  const formData = new FormData();
  formData.append("file", file);

  let res: Response;
  try {
    res = await fetch(`${BASE_URL}/api/incidents/analyze`, {
      method: "POST",
      body: formData,
    });
  } catch {
    throw new Error("Could not reach the analysis service. Is the API running?");
  }

  if (!res.ok) {
    throw new Error(await parseErrorDetail(res));
  }

  return (await res.json()) as AnalysisSummary;
}

export function exportResultsUrl(): string {
  return `${BASE_URL}/api/incidents/results/export`;
}
