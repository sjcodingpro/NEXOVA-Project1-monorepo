"""Nexova sales knowledge base: retrieval and answer generation (Milestone 7).

- ``retrieve()``         embeds the question, searches ``nexova_knowledge``, drops hits
                         below ``min_score`` and returns plain payload dicts.
- ``generate_answer()``  builds the salesperson prompt from those payloads and calls the
                         generation model. The LangGraph agent will call it as its own node.
- ``query()``            the only entry point for the API and UI: retrieve() + generate_answer().

Raw Qdrant hits and scores never leave this module (they are logged at DEBUG only).
"""
from __future__ import annotations

import logging
import os
from functools import lru_cache

from data.process.rag import COLLECTION, COMPANY, embed, embedding_model, get_qdrant_client

logger = logging.getLogger("nexova.rag")

DEFAULT_K = 5
# Cosine similarity floor. Tuned with data/eval/rag_recall.py; see docs/rag/rag-design.md.
DEFAULT_MIN_SCORE = float(os.environ.get("RAG_MIN_SCORE", "0.30"))

NO_CONTEXT_MARKER = "NO RELEVANT CONTEXT FOUND"

# Used only when retrieve() returns nothing above min_score. With no context, the model has
# nothing true to say about Nexova, so it may not describe the company at all.
NO_CONTEXT_INSTRUCTION = """\
The knowledge base has NO information for this question. Reply in at most two short sentences:
say that Nexova's sales knowledge base doesn't cover this, and suggest the SDR check with a
senior account manager before answering the prospect. Do NOT state anything about Nexova:
no services it does or doesn't offer, no prices, timelines, partners, policies or opinions,
and do not guess. End with the line "Source: none (not covered by the knowledge base)".
"""

SYSTEM_PROMPT = """\
You are a Nexova salesperson helping an SDR or account manager before or during a call
with a prospect. Nexova is an HR consulting and talent acquisition firm (Valencia, Spain
and Miami, US). Answer the way a confident, closing-oriented Nexova salesperson would:
clear, warm, concise, and focused on moving the prospect to the next step.

Rules you must never break:
1. Use ONLY the facts in the CONTEXT block. Every percentage, amount, fee, timeframe and
   guarantee you mention must appear in the context exactly as written. Never round,
   estimate or combine numbers into new ones.
2. Never offer, promise or hint at a discount, fee below 22%, or any commercial condition
   that is not in the context. If the prospect asks for one, say that it is not a standard
   condition and that it needs approval from Nexova's sales leadership, then offer to
   escalate it.
3. Present delivery and process times as averages or typical figures, never as guarantees.
   The only guarantee you may present as contractual is the 6-month replacement guarantee,
   and only as the context describes it.
4. When a prospect asks about competitors' clients or other clients, keep exactly the level
   of transparency the context describes. Do not name or reveal anything beyond it.
5. If the context does not answer the question, or it says NO RELEVANT CONTEXT FOUND, say
   plainly that the knowledge base doesn't have that information and suggest checking with a
   senior account manager. Do not guess, and never describe Nexova's services, partners or
   policies from general knowledge: only the context counts as true.
6. Do not mention "context", "chunks" or "documents"; speak as the salesperson. At the end,
   add one line "Source:" naming the document section(s) you used, e.g.
   "Source: pricing-model / Executive search fee".
"""


# ======================================================================================
# retrieve()
# ======================================================================================
def _search(*, vector: list[float], limit: int) -> list:
    """The single Qdrant call (unit tests replace this function)."""
    from qdrant_client import models

    return get_qdrant_client().query_points(
        collection_name=COLLECTION,
        query=vector,
        limit=limit,
        with_payload=True,
        query_filter=models.Filter(must=[
            models.FieldCondition(key="company", match=models.MatchValue(value=COMPANY)),
        ]),
    ).points


def retrieve(query: str, *, k: int = DEFAULT_K, min_score: float = DEFAULT_MIN_SCORE) -> list[dict]:
    """Top-k chunk payloads for ``query`` whose cosine similarity is at least ``min_score``.
    May return fewer than k, or none: a weak match is worse than no match for a salesperson."""
    hits = _search(vector=embed(query), limit=k)
    for hit in hits:
        logger.debug("rag hit score=%.3f %s / %s", hit.score,
                     (hit.payload or {}).get("source_document"), (hit.payload or {}).get("section"))
    return [dict(hit.payload) for hit in hits if hit.score >= min_score]


# ======================================================================================
# generate_answer()
# ======================================================================================
def build_prompt(question: str, context: list[dict]) -> str:
    """User message: the retrieved chunks, each labelled with its source, then the question."""
    if not context:
        return (f"CONTEXT:\n---\n{NO_CONTEXT_MARKER}\n---\n\n"
                f"QUESTION FROM THE SDR:\n{question.strip()}\n\n"
                f"{NO_CONTEXT_INSTRUCTION}")
    blocks = [f"[{c.get('source_document', '?')} / {c.get('section', '?')}]\n{c.get('text', '').strip()}"
              for c in context]
    context_text = "\n\n---\n\n".join(blocks)
    return f"CONTEXT:\n---\n{context_text}\n---\n\nQUESTION FROM THE SDR:\n{question.strip()}"


@lru_cache(maxsize=1)
def _generation_client():
    from openai import OpenAI

    return OpenAI(base_url=os.environ["RAG_BASE_URL"], api_key=os.environ["RAG_API_KEY"])


def generation_model() -> str:
    model = os.environ["RAG_GEN_MODEL"]
    if model == embedding_model():
        raise RuntimeError("RAG_GEN_MODEL must be a chat/generation model, not the embeddings model.")
    return model


def _generate(prompt: str) -> str:
    """One call to the generation (chat) model (unit tests replace this function)."""
    response = _generation_client().chat.completions.create(
        model=generation_model(),
        messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
        temperature=0.2,
    )
    return (response.choices[0].message.content or "").strip()


def generate_answer(question: str, context: list[dict]) -> str:
    """Salesperson answer for ``question`` grounded only in ``context`` (may be empty)."""
    return _generate(build_prompt(question, context))


# ======================================================================================
# query()
# ======================================================================================
def query(question: str) -> str:
    """The only function the API and UI call: retrieve() then generate_answer()."""
    return generate_answer(question, retrieve(question))
