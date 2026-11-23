"""Unit tests for the Nexova RAG pipeline (data/process/rag.py, data/pipelines/rag.py).

No Qdrant, no model API: the Qdrant search, embed() and the generation call are all
replaced with stubs.

Run: python -m pytest tests/pipelines/test_rag.py -v   (from the repo root)
"""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from data.pipelines import rag  # noqa: E402
from data.process import rag as process_rag  # noqa: E402


def hit(score, source="pricing-model", section="Fees", text="Our fee is 22%."):
    return SimpleNamespace(score=score, payload={
        "company": "nexova", "source_document": source, "section": section,
        "language": "en", "chunk_index": 0, "text": text})


@pytest.fixture
def no_embeddings(monkeypatch):
    calls = []
    monkeypatch.setattr(rag, "embed", lambda text: calls.append(text) or [0.1, 0.2, 0.3])
    return calls


# --------------------------------------------------------------------------- retrieve()
def test_retrieve_excludes_hits_below_min_score(monkeypatch, no_embeddings):
    monkeypatch.setattr(rag, "_search", lambda **kw: [hit(0.82, section="A"), hit(0.40, section="B")])
    result = rag.retrieve("What is the fee?", k=5, min_score=0.45)
    assert [r["section"] for r in result] == ["A"]


def test_retrieve_can_return_fewer_than_k(monkeypatch, no_embeddings):
    monkeypatch.setattr(rag, "_search", lambda **kw: [hit(0.9), hit(0.7), hit(0.3), hit(0.2), hit(0.1)])
    result = rag.retrieve("fee", k=5, min_score=0.5)
    assert len(result) == 2 < 5


def test_retrieve_returns_empty_list_when_nothing_clears_threshold(monkeypatch, no_embeddings):
    monkeypatch.setattr(rag, "_search", lambda **kw: [hit(0.2), hit(0.1)])
    assert rag.retrieve("weather in Valencia", min_score=0.45) == []


def test_retrieve_returns_plain_payload_dicts_not_qdrant_objects(monkeypatch, no_embeddings):
    monkeypatch.setattr(rag, "_search", lambda **kw: [hit(0.9)])
    [result] = rag.retrieve("fee", min_score=0.5)
    assert type(result) is dict
    assert {"source_document", "section", "company", "language", "chunk_index", "text"} <= result.keys()
    assert "score" not in result


def test_retrieve_embeds_the_question_and_asks_for_k(monkeypatch, no_embeddings):
    seen = {}
    monkeypatch.setattr(rag, "_search", lambda **kw: seen.update(kw) or [])
    rag.retrieve("How long does a search take?", k=3, min_score=0.5)
    assert no_embeddings == ["How long does a search take?"]
    assert seen == {"vector": [0.1, 0.2, 0.3], "limit": 3}


# ------------------------------------------------------------------------------ query()
def test_query_returns_the_model_output(monkeypatch):
    monkeypatch.setattr(rag, "retrieve", lambda q: [{"source_document": "pricing-model",
                                                     "section": "Fees", "text": "Fee: 22% of salary."}])
    monkeypatch.setattr(rag, "_generate", lambda prompt: "Our fee is 22% of the first-year salary.")
    assert rag.query("What's your fee?") == "Our fee is 22% of the first-year salary."


def test_query_never_returns_raw_chunk_text(monkeypatch):
    chunk_text = "RAW CHUNK: Fee is 22% of gross annual salary."
    monkeypatch.setattr(rag, "retrieve", lambda q: [{"source_document": "pricing-model",
                                                     "section": "Fees", "text": chunk_text}])
    prompts = []
    monkeypatch.setattr(rag, "_generate", lambda prompt: prompts.append(prompt) or "Generated answer")
    answer = rag.query("What's your fee?")
    assert answer == "Generated answer"
    assert chunk_text not in answer
    assert len(prompts) == 1 and chunk_text in prompts[0]  # the chunk went to the model, not the caller


def test_query_is_retrieve_then_generate_answer(monkeypatch):
    context = [{"source_document": "hiring-process-sla", "section": "Timeline", "text": "x"}]
    monkeypatch.setattr(rag, "retrieve", lambda q: context)
    seen = {}
    monkeypatch.setattr(rag, "generate_answer", lambda q, c: seen.update(q=q, c=c) or "ok")
    assert rag.query("How long?") == "ok"
    assert seen == {"q": "How long?", "c": context}


def test_query_with_no_context_still_goes_through_the_model(monkeypatch):
    monkeypatch.setattr(rag, "retrieve", lambda q: [])
    prompts = []
    monkeypatch.setattr(rag, "_generate",
                        lambda prompt: prompts.append(prompt) or "I don't have that information.")
    assert rag.query("What's the weather in Valencia?") == "I don't have that information."
    assert rag.NO_CONTEXT_MARKER in prompts[0]
    assert rag.NO_CONTEXT_INSTRUCTION in prompts[0]   # strict "state no Nexova facts" instruction


def test_no_context_instruction_forbids_inventing_company_facts():
    i = rag.NO_CONTEXT_INSTRUCTION
    assert "doesn't cover" in i and "senior account manager" in i
    assert "Do NOT state anything about Nexova" in i
    assert rag.NO_CONTEXT_INSTRUCTION not in rag.build_prompt("Fee?", [{"text": "22%"}])


def test_prompt_labels_each_chunk_with_its_source():
    prompt = rag.build_prompt("Fee?", [{"source_document": "pricing-model", "section": "Fees", "text": "22%"}])
    assert "[pricing-model / Fees]" in prompt and "22%" in prompt and "Fee?" in prompt


def test_system_prompt_encodes_briefing_constraints():
    p = rag.SYSTEM_PROMPT
    assert "Nexova salesperson" in p
    assert "22%" in p and "approval" in p              # no discount below the 22% fee
    assert "averages" in p and "6-month replacement guarantee" in p
    assert "ONLY" in p                                  # grounded in retrieved context


# ----------------------------------------------------------------------------- chunking
DOC = """# Pricing Model

Intro paragraph about how Nexova prices its services.

## Executive search

The fee is 22% of the first-year gross salary.

| Item | Value |
|---|---|
| Fee | 22% |
| Retainer | one third |

## Guarantees

### Replacement

If the candidate leaves within 6 months, we replace them at no cost.

### Short note

Tiny.
"""


def test_chunks_follow_headings_and_keep_tables_whole():
    chunks = process_rag.chunk_document(DOC, "pricing-model")
    sections = [c.section for c in chunks]
    assert sections[0] == "Pricing Model"            # text before the first ## -> the # title
    assert "Executive search" in sections
    table = next(c for c in chunks if "| Fee | 22% |" in c.text)
    assert table.section == "Executive search" and "| Retainer | one third |" in table.text
    assert all(c.source_document == "pricing-model" and c.language == "en" for c in chunks)


def test_long_section_is_split_between_blocks_never_inside_one(monkeypatch):
    monkeypatch.setattr(process_rag, "MAX_CHUNK_CHARS", 60)
    paragraphs = [f"Rule {i}: condition A applies and condition B applies too." for i in range(4)]
    doc = "## Rules\n\n" + "\n\n".join(paragraphs)
    chunks = process_rag.chunk_document(doc, "service-lines")
    assert len(chunks) == 4
    assert [c.text for c in chunks] == paragraphs          # every rule intact
    assert [c.chunk_index for c in chunks] == [0, 1, 2, 3]


def test_point_ids_are_deterministic():
    a = process_rag.chunk_document(DOC, "pricing-model")
    b = process_rag.chunk_document(DOC, "pricing-model")
    assert [c.point_id for c in a] == [c.point_id for c in b]
    assert len({c.point_id for c in a}) == len(a)


NEXOVA_STYLE = """# Pricing Model

Executive headhunting:
- Standard fee: 22% of the hired role's gross annual salary.
- Billed in three installments: 30% when the search begins, 30% when the
  final shortlist is presented, 40% upon hire.

Corporate training:
- 4-week program: starting at 3,500 USD for groups of up to 15 people.

# ignored second title

Intro line:

1. Executive headhunting: search and selection. Average delivery time: 6 to 8 weeks.

2. Customer support outsourcing: minimum contractable team size: 5 agents.

"22% seems expensive compared to other firms."
Suggested response: explain the 6-month replacement guarantee.
"""


def test_headingless_documents_split_at_labelled_units():
    chunks = process_rag.chunk_document(NEXOVA_STYLE, "pricing-model")
    by_section = {c.section: c.text for c in chunks}
    assert set(by_section) == {
        "Pricing Model › Executive headhunting",
        "Pricing Model › Corporate training",
        "Pricing Model › Executive headhunting",
        "Pricing Model › Customer support outsourcing",
        "Pricing Model › 22% seems expensive compared to other firms.",
    }
    fee = next(c.text for c in chunks if "Standard fee" in c.text)
    assert "40% upon hire" in fee                             # the whole installment rule stays together
    objection = by_section["Pricing Model › 22% seems expensive compared to other firms."]
    assert "Suggested response" in objection                  # objection kept with its response
    numbered = [c for c in chunks if c.text.startswith("Intro line:")]
    assert len(numbered) == 1 and "1. Executive headhunting" in numbered[0].text  # lead-in joined


def test_real_knowledge_base_meets_briefing_minimums():
    chunks = process_rag.load_chunks()
    counts = {}
    for c in chunks:
        counts[c.source_document] = counts.get(c.source_document, 0) + 1
    assert set(counts) == {"service-lines", "pricing-model", "hiring-process-sla", "objection-handling"}
    assert all(n >= 3 for n in counts.values()), counts      # BRIEFING section 5
    assert all(c.payload()["section"] and c.payload()["text"] and c.payload()["company"] == "nexova"
               for c in chunks)
    assert len({c.point_id for c in chunks}) == len(chunks)
