import { apiFetch } from "@/lib/api-client";
import type { KnowledgeQueryResponse } from "@/types/knowledge";

/** Ask the sales knowledge base. Returns only the model-generated answer. */
export function askSalesAssistant(question: string): Promise<KnowledgeQueryResponse> {
  return apiFetch<KnowledgeQueryResponse>("/knowledge/query", {
    method: "POST",
    body: JSON.stringify({ question }),
  });
}
