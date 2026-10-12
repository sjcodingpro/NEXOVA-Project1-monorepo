import { apiFetch } from "@/lib/api-client";
import type { WeeklyPerformance } from "@/types/reporting";

/** KPI rows for one ISO week (a Monday). Without an argument: the most recent computed week. */
export function getWeeklyOfficeProgramPerformance(weekStart?: string): Promise<WeeklyPerformance> {
  const qs = weekStart ? `?week_start=${encodeURIComponent(weekStart)}` : "";
  return apiFetch<WeeklyPerformance>(`/reporting/weekly-office-program-performance${qs}`);
}
