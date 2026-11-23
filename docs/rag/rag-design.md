# Nexova Sales Knowledge Base: RAG design

**Who it's for:** Nexova's SDRs and account managers (Marcos Ibáñez's sales team, 18 people). They
ask what a prospect just asked them and get an answer in the voice of a Nexova salesperson: confident
and closing-oriented, but never inventing commercial terms.

**Stack:** Qdrant (vector store) · the 4Geeks LLM gateway (embeddings + generation) · FastAPI ·
Next.js backoffice. No LangChain/LlamaIndex: the four steps are plain Python functions.

| Piece | Where |
|---|---|
| Source documents | `docs/company-knowledge-base/` (4 files from `00-general-contexts/nexova/`) |
| `setup()`, `embed()` | `data/process/rag.py` |
| `retrieve()`, `generate_answer()`, `query()` | `data/pipelines/rag.py` |
| `POST /knowledge/query` | `services/api/app/knowledge/router.py` |
| Query UI | `uis/backoffice/app/knowledge/page.tsx` (nav: **Sales Assistant**) |
| Unit tests | `tests/pipelines/test_rag.py` |
| Retrieval eval | `data/eval/test-queries.json`, `data/eval/rag_recall.py`, `data/eval/rag_recall_report.json` |

---

## 1. RAG process

```
docs/company-knowledge-base/*.md
        │  setup()   (data/process/rag.py, run once / after any doc change)
        ▼
  semantic chunks ──embed()──► Qdrant collection "nexova_knowledge" (15 points)
                                        ▲
SDR question (UI) ─► POST /knowledge/query ─► query(question)
                                        │
                     retrieve(question) ─┤ embed(question) → top-5 cosine search,
                                        │ drop hits below min_score → payload dicts
                                        ▼
                     generate_answer(question, chunks) → salesperson prompt → chat model
                                        ▼
                                  {"answer": "..."}  (generated text only)
```

1. **Source corpus.** The four BRIEFING documents (service lines, pricing model, hiring-process SLA,
   objection handling) are copied unchanged from `00-general-contexts/nexova/` into
   `docs/company-knowledge-base/`. `setup()` fails loudly if any of them is missing.
2. **`setup()`** reads each file, splits it into semantic chunks (section 2), embeds every chunk with
   `embed()` and upserts it into `nexova_knowledge` with the BRIEFING payload: `company`,
   `source_document`, `section`, `language`, `chunk_index`, plus `text` for prompt assembly.
   - **Idempotent by deterministic ids.** Each point id is `uuid5(company | source_document |
     section | chunk_index)`, so a re-run overwrites the same points instead of duplicating them.
     Points whose section no longer exists are deleted. If the embeddings model (vector size)
     changes, the collection is recreated.
   - Run: `uv run python -m data.process.rag`. It prints the collection stats.
3. **`retrieve(query, k=5, min_score=0.30)`** embeds the question with the same `embed()`, runs a
   cosine search filtered to `company = nexova`, drops every hit below `min_score` and returns
   plain payload dicts. It can return fewer than k results, or none. Scores are logged at DEBUG
   only and never leave the module.
4. **`generate_answer(question, context)`** builds the prompt (section 4) and calls the chat model.
   It is a separate function so the future LangGraph agent can run retrieval and generation as two
   nodes.
5. **`query(question)`** is literally `generate_answer(question, retrieve(question))`. It is the only
   function the API and UI call.
6. **`POST /knowledge/query`** takes `{"question": "..."}` and returns `{"answer": "..."}`. The router
   imports `query()` and contains no retrieval or generation logic. Failures (Qdrant down, model
   error) return a 503 with a readable message, never an empty answer.

## 2. Chunking strategy

**The corpus:** four short documents (860–1,240 characters each). Each has one `#` title and
**no `##` sub-headings**. Their meaning lives in blank-line-separated units instead:

| Document | Natural unit | Chunks |
|---|---|---|
| `nexova-service-lines.en.md` | one numbered service line (scope + delivery time / minimums), plus the closing "contracted independently" rule | 4 |
| `nexova-pricing-model.en.md` | one labelled price block ("Executive headhunting:" + its bullets) | 3 |
| `nexova-hiring-process-sla.en.md` | the delivery-times list, and each policy paragraph (averages-not-guarantees, 4-week escalation, geographic exception) | 4 |
| `nexova-objection-handling.en.md` | one objection quote + its response | 4 |

**15 chunks in total.** Every document has at least 3, as BRIEFING section 5 requires. They run from
88 to 358 characters (about 20–90 tokens).

**How the splitter works** (`chunk_document()`):

1. Split at `##` / `###` headings when there are any. Text before the first `##` belongs to the
   document title. This keeps the code correct if a future document does use sub-headings.
2. Inside each section, every blank-line-separated block is one semantic unit, and **a unit is never
   cut**. A bullet list, a numbered item or an objection with its response stays whole, so no rule
   loses its condition. Examples that stay together: "30% / 30% / 40%" with the events that trigger
   each installment; the 22% fee with its replacement guarantee; the objection with "never offer a
   discount below 22% without Marcos Ibáñez's approval".
3. A one-line lead-in ending in `:` ("Committed delivery times by search type:") is joined to the
   list it introduces.
4. The unit's own label becomes its `section` name: the service line name, the pricing block, or the
   objection itself, e.g. `Pricing Model › Executive headhunting`. Unlabelled policy paragraphs keep
   the document title, and `chunk_index` tells them apart.
5. Only a unit longer than 1,400 characters would be split, and only between whole lines or list
   items. None of the current units is anywhere near that size.

**Why not fixed-size chunks:** a 500-character window would cut "Billed in three installments: 30%
when the search begins, 30% when…" in half, or separate an objection from its response. Then the
model either refuses or fills the gap from general knowledge. Unit-level chunks are small enough
that the top 3 hits stay focused, and complete enough that each one can be quoted alone.

**What gets embedded** is `"<document>: <section>\n\n<text>"`. Prefixing the section name gives short
units their topic back (e.g. the bare SLA paragraph "These times are averages…" becomes clearly about
hiring-process SLAs). The payload `text` stays the original wording for the prompt.

## 3. Embedding practices

| | |
|---|---|
| Embeddings model | `downtown-miami/openrouter/perplexity/pplx-embed-v1-0.6b` (4Geeks LLM gateway) |
| Generation model | `downtown-miami/openrouter/deepseek/deepseek-v4-flash` (4Geeks LLM gateway) |
| Gateway | `https://llm.4geeks.ai/v1` (LiteLLM, OpenAI-compatible), student key in `.env` |
| Vector size | 1,024 (detected from the first embedding; the collection is created to match) |
| Distance | Cosine |
| `min_score` | **0.30** (env `RAG_MIN_SCORE`) |
| `k` | 5 at query time; 3 in the Recall@3 eval |

- **Two different models.** Both are 4Geeks-provided, through the student LLM gateway. `embedding_model()`
  and `generation_model()` raise an error if `RAG_EMBED_MODEL` and `RAG_GEN_MODEL` are ever set to
  the same id.
- **One `embed()` for both sides.** `setup()` embeds chunks and `retrieve()` embeds the SDR's question
  with the same function, model and preprocessing.
- **Preprocessing:** whitespace is collapsed to single spaces before embedding (so line wraps in the
  Markdown don't change vectors). No lower-casing or stemming: the model handles that.
- **Gateway note:** the 4Geeks dashboard shows model ids with a `litellm/` prefix, but the gateway
  only accepts them without it. The real ids come from `GET /v1/models` (command in `.env.example`).
  `glm-5.3-flash` is listed but rejected by the gateway, so generation uses `deepseek-v4-flash`.

### How `min_score` was tuned

`uv run python -m data.eval.rag_recall` embeds the 14 test questions plus 3 off-topic questions
and records the cosine similarity of every top-3 hit (`data/eval/rag_recall_report.json`):

| | Similarity |
|---|---|
| Correct chunk, all 13 retrieved questions | 0.371 – 0.666 |
| Best hit for off-topic questions (weather, Python libraries, payroll/tax services) | ≤ 0.182 |
| Other (non-expected) chunks in the top 3 | 0.23 – 0.60, median 0.28 |

**0.30** sits between the two groups. It keeps every correct chunk (lowest 0.371, the SLA
"averages, not guarantees" paragraph), rejects every off-topic question by a wide margin (so
"Do you offer payroll processing?" gets the honest "we don't have that information"), and trims the
weakest neighbouring chunks (about half of them score below 0.30) out of the prompt. The default first value of 0.45 was too strict: it
would have dropped the correct chunk for two SLA questions.

## 4. Generation prompt and business rules

The system prompt (`SYSTEM_PROMPT` in `data/pipelines/rag.py`) makes the model a **Nexova
salesperson briefing an SDR**: confident, warm, concise and closing-oriented. It encodes every
BRIEFING constraint:

- **Faithfulness:** answer only from the context. Every percentage, amount, fee, timeframe and
  guarantee must appear in the context exactly as written.
- **No discounts below the 22% fee:** say it isn't a standard condition, that it needs sales
  leadership approval, and offer to escalate.
- **Times are averages,** never guarantees. The only contractual guarantee is the 6-month
  replacement guarantee, as the documents describe it.
- **Competitors:** keep exactly the transparency the objection-handling guide describes.
- **No context → no answer.** When `retrieve()` returns nothing above 0.30, the prompt carries
  `NO RELEVANT CONTEXT FOUND`, and the model must say the knowledge base doesn't have that
  information and suggest a senior account manager.
- Each answer ends with a `Source:` line naming the document section used, so it's traceable.

Each chunk in the prompt is labelled `[source_document / section]`.

## 5. Evaluation

`data/eval/test-queries.json`: 14 questions across all four documents, plus 3 off-topic. Four of them
are real objections from `nexova-objection-handling.en.md` ("22% seems expensive…", the shortlist,
paying at the end, competitors). Each names its exact expected chunk (`source_document` +
`section`, + `chunk_index` where a section has several).

**Recall@3 = 13/14 = 93%** (target ≥ 80%). 12 of the 13 hits are at rank 1.

The miss is `sl-3`, "Can we hire only your training service without the recruiting one?". The
answer is the 88-character closing sentence of service lines ("Each service line is contracted
independently…"), and the question's wording pulled the SLA paragraphs above it. It is left as a
known weakness rather than tuned away. A fix, if needed, would be attaching that closing rule to
each service-line chunk.

## 6. Running it

```bash
docker compose up -d qdrant                  # vector store on :6333
uv run python -m data.process.rag            # index (idempotent)
uv run python -m data.eval.rag_recall        # Recall@3 + score distributions
uv run python -m pytest tests/pipelines/test_rag.py -q
cd services/api && uv sync && uv run uvicorn app.main:app --reload    # API on :8000
cd uis/backoffice && npm run dev             # UI → /knowledge
```

`.env` needs `RAG_BASE_URL`, `RAG_API_KEY`, `RAG_EMBED_MODEL`, `RAG_GEN_MODEL`, `QDRANT_URL` and
`RAG_MIN_SCORE` (see `.env.example`). Under `docker compose`, the backend reaches Qdrant at
`http://qdrant:6333` and mounts `data/` read-only at `/repo/data`.
