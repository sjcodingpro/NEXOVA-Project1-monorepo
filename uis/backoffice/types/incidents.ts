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
