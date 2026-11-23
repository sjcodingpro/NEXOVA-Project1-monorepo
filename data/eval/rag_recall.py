"""Recall@3 for the Nexova sales knowledge base, plus the evidence for min_score.

For every question in data/eval/test-queries.json, retrieve the top 3 chunks with no
threshold (min_score=0) and count a hit when one of them is the expected chunk: same
source_document, section and (when given) chunk_index. BRIEFING target: >= 80%.

Off-topic questions (expected_source_document = null) aren't counted in Recall@3. Their
best similarity shows how high an unrelated question scores, which is what min_score must
stay above. The report prints both distributions so the threshold choice is visible.

Needs Qdrant indexed by setup() and the embeddings model configured in .env.
Run from the repo root:  uv run python -m data.eval.rag_recall
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from data.pipelines.rag import DEFAULT_MIN_SCORE, _search
from data.process.rag import COLLECTION, embed, embedding_model

EVAL_DIR = Path(__file__).resolve().parent
QUERIES = EVAL_DIR / "test-queries.json"
REPORT = EVAL_DIR / "rag_recall_report.json"
K = 3


def is_match(payload: dict, case: dict) -> bool:
    """Exactly the expected chunk: same document and section, and the same chunk_index
    when that section has several chunks (e.g. the unlabelled SLA policy paragraphs)."""
    return (payload.get("source_document") == case["expected_source_document"]
            and payload.get("section") == case["expected_section"]
            and ("expected_chunk_index" not in case
                 or payload.get("chunk_index") == case["expected_chunk_index"]))


def main() -> None:
    cases = json.loads(QUERIES.read_text(encoding="utf-8"))
    rows = []
    for case in cases:
        hits = _search(vector=embed(case["question"]), limit=K)
        top = [{"source_document": h.payload["source_document"], "section": h.payload["section"],
                "score": round(float(h.score), 4)} for h in hits]
        expected_doc = case.get("expected_source_document")
        row = {"id": case["id"], "question": case["question"], "top3": top,
               "best_score": top[0]["score"] if top else 0.0}
        if expected_doc:
            ranks = [i + 1 for i, h in enumerate(hits)
                     if is_match(h.payload, case)]
            row |= {"expected": f"{expected_doc} / {case['expected_section']}",
                    "hit": bool(ranks), "rank": ranks[0] if ranks else None,
                    "correct_score": top[ranks[0] - 1]["score"] if ranks else None}
        rows.append(row)

    scored = [r for r in rows if "hit" in r]
    off_topic = [r for r in rows if "hit" not in r]
    hits = sum(r["hit"] for r in scored)
    recall = hits / len(scored)
    correct_scores = sorted(r["correct_score"] for r in scored if r["correct_score"] is not None)
    off_scores = sorted(r["best_score"] for r in off_topic)

    print(f"Collection {COLLECTION}, embeddings model {embedding_model()}\n")
    for r in scored:
        mark = f"HIT  rank {r['rank']}" if r["hit"] else "MISS      "
        print(f"{mark}  {r['id']:<6} {r['question'][:70]}")
        if not r["hit"]:
            for t in r["top3"]:
                print(f"            got {t['score']:.3f}  {t['source_document']} / {t['section']}")
    print(f"\nRecall@{K}: {hits}/{len(scored)} = {recall:.0%}  (BRIEFING target >= 80%)")
    print(f"Similarity of the correct chunk:     min {correct_scores[0]:.3f}  max {correct_scores[-1]:.3f}")
    if off_scores:
        print(f"Best similarity, off-topic questions: max {off_scores[-1]:.3f}  ({len(off_scores)} questions)")
    print(f"Current min_score: {DEFAULT_MIN_SCORE}")
    below = [r["id"] for r in scored if r["correct_score"] is not None and r["correct_score"] < DEFAULT_MIN_SCORE]
    above = [r["id"] for r in off_topic if r["best_score"] >= DEFAULT_MIN_SCORE]
    print(f"  correct chunks it would drop: {below or 'none'}")
    print(f"  off-topic questions it would let through: {above or 'none'}")

    REPORT.write_text(json.dumps({
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "collection": COLLECTION, "embedding_model": embedding_model(), "k": K,
        "recall_at_3": round(recall, 4), "hits": hits, "questions": len(scored),
        "min_score": DEFAULT_MIN_SCORE,
        "correct_chunk_score_range": [correct_scores[0], correct_scores[-1]],
        "off_topic_best_score_max": off_scores[-1] if off_scores else None,
        "results": rows,
    }, indent=2), encoding="utf-8")
    print(f"\nWrote {REPORT.relative_to(EVAL_DIR.parents[1])}")


if __name__ == "__main__":
    main()
