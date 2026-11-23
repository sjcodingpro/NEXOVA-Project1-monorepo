/** POST /knowledge/query response: the generated answer only (never chunks or scores). */
export interface KnowledgeQueryResponse {
  answer: string;
}
