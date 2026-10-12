export interface WeeklyPerformanceEntry {
  office: string;
  programme_id: string;
  total_material_cost: number;
  kits_delivered_count: number;
  shortage_events_count: number;
  cost_variance_events_count: number;
  currency: string;
}

export interface WeeklyPerformance {
  week_start: string | null;
  entries: WeeklyPerformanceEntry[];
}
