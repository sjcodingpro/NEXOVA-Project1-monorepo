# Progress — Nexova Monorepo

## Completed

### uis/website
- Landing page and talent registration form built to spec (English +
  Spanish), Tailwind-styled, Schema.org markup present, form validation
  matching every rule in CONTEXT.md.
- Migrated from repo root into `uis/website/` (this milestone) to match
  monorepo folder conventions. Verified locally post-move: both pages
  render correctly, form validation still fires correctly.

### uis/talent-pipeline-tracker
- Full milestone delivered: candidate list (filter/search via URL
  params), candidate detail (status/stage PATCH, notes add/delete),
  register (POST) and edit (PUT) forms with validation, optional
  delete-candidate action.
- Fully typed against the real Talent Tracker API shapes (confirmed via
  live Swagger responses, not assumed from schema alone).
- Clean production build, zero ESLint errors, zero `any`, 100%
  async/await (no `.then`/`.catch` chains).
- Pushed to `main` and merged.

### uis/backoffice
- New minimal internal app: Next.js App Router + TypeScript + Tailwind,
  own layout distinct from uis/website, entry view rendering a real
  company snapshot (founding year, headcount, revenue, both office
  locations, all three business lines) sourced from CONTEXT.md.
- Clean production build.
- Scaffolded using the `.agents/skills/scaffold-uis-app` skill — first
  real use of that skill, confirming its steps actually work end to
  end (install, README, build verification).
- Gotcha hit and fixed: the Tailwind v4 create-next-app scaffold ships
  an unlayered `body { background; color; }` rule in `globals.css`
  that overrides Tailwind utility classes applied to `<body>`
  regardless of specificity, because it sits outside any `@layer`.
  Fix: remove the scaffold's hardcoded body styling and control body
  appearance via Tailwind classes in `layout.tsx` instead. Worth
  checking for on any future Next.js + Tailwind v4 scaffold in this
  repo.

## In progress (this milestone — agent infrastructure)

- [x] `CONTEXT.md` confirmed as the real Nexova briefing (not the
      template placeholder) — no action needed, already correct.
- [x] `memory-bank/projectbrief.md` — business context
- [x] `memory-bank/techContext.md` — technical context
- [x] `memory-bank/progress.md` — this file, kept updated as work
      progressed
- [x] `AGENTS.md` at repo root — mandatory read list, 6-step pre-commit
      workflow, do-not-touch list
- [x] `.agents/rules/` — no-raw-api-values-in-ui.md
- [x] `.agents/skills/<skill>/SKILL.md` — scaffold-uis-app, used for
      real on uis/backoffice
- [x] `uis/backoffice/` — new app, own layout, `/` entry view, real
      Nexova data visible on screen
- [x] Run the AGENTS.md delivery workflow before final commit
- [ ] Open PR from `feature/agent-memory-bank` → `main` with required
      screenshots + AGENTS.md link

## Sales forecast model (`feature/sales-forecast-model`, 2026-11-06)

- [x] `data/raw/nexova_sales.csv` added as provided (120 consolidated rows, 2016-01..2025-12)
- [x] Root `pyproject.toml` + `uv.lock` created with `uv init --bare` / `uv add` for the ML
      tooling (pandas, numpy, scikit-learn, xgboost, matplotlib, pytest dev). Independent of
      `services/api`'s own uv project. Use uv only — no pip/pipenv.
- [x] `scripts/train_sales_forecast.py` — Random Forest, 8y train / 2y test, recursive 24-month
      forecast with P5-P95 tree band; outputs in `data/eval/sales_forecast/`
- [x] `tests/pipelines/test_sales_forecast.py` — 8/2 split + leakage tests
- [x] `scripts/SALES_FORECAST.md` — model choice, metrics and their meaning
- [ ] PR → `main`, pending tech-lead review
- Decision: same-month `active_contracts` / `avg_contract_value_usd` are excluded as features —
  their product reproduces `revenue_usd` (target leakage).
- Confirmed with developer: "K2 Score" in the ticket is a typo for R² (coefficient of determination).
- Decision: PSI uses >=5 obs/bin (4 bins on 24 test months); 10 bins is noise-dominated there.

## Known open items / decisions made along the way

- Decided **not** to fold `talent-pipeline-tracker` into `backoffice` —
  kept as two separate apps under `uis/`. Rationale: this milestone's
  scope is agent infrastructure + a minimal backoffice shell, not a
  consolidation of an already-shipped, evaluated project.
- `00-general-contexts/` (referenced by this milestone's README as the
  source of the company briefing) does not exist in this fork — moot,
  since `CONTEXT.md` was already correctly populated with the real
  briefing.
- Root-level `pagespeed-nexova1.png` (a performance report screenshot
  from an earlier ad hoc check) was moved into `uis/website/` alongside
  the site it documents, rather than left orphaned at repo root.
- Vercel deployment (if ever reconnected) will need its Root Directory
  setting updated to `uis/website` post-move — not a code change, a
  dashboard setting, out of scope for this repo.

## Next steps after this milestone

- Decide and build out `uis/backoffice` beyond its minimal entry view
  (auth, people management, operations tooling) when a specific ticket
  calls for it.
- Earlier course material referenced a future RAG/knowledge-base
  milestone for Nexova's Sales team (service lines, pricing model,
  hiring-process SLA, objection handling) — not started, not part of
  this repo's current state, noted here in case a future agent session
  needs the context that it's coming.

## Sales forecast evaluation (`feature/regression-model-eval`, 2026-11-18)

- [x] `scripts/evaluate_sales_forecast.py` — 5-fold `TimeSeriesSplit` (one calendar year per fold) on
      2016-2023 only, features rebuilt per fold from the truncated series, learning curve with OOB error,
      MAE/RMSE train + validation, `min_samples_leaf` sweep. Outputs in `data/eval/`.
- [x] `tests/pipelines/test_model_evaluation.py` — fold chronological order, no leakage, min-window guard
- [x] `.github/workflows/pipeline-tests.yml` — CI runs `tests/pipelines` with uv on every PR
- [x] Diagnosis: reasonably well fitted (val MAE $26.1k ± $1.5k on folds with >= 24 training months; OOB
      converges onto validation). Unstable below 24 feature months (fold 1: $64.6k).
- [x] Corrective action: `MIN_TRAIN_FEATURE_MONTHS = 24` guard in `train_model`; expanding-window retraining.
- Decision: no extra regularisation (raises validation error) and no "growth-to-date" feature (tested, no gain).
- [x] Primary metric: RMSE (briefing states no over/under asymmetry; it stresses telling a normal August from
      an anomalous drop, so large single-month misses are the costly error). MAE reported alongside.
- Branch is stacked on `feature/sales-forecast-model` because PR #24 was not merged yet.

## Sales knowledge base / RAG (`feature/rag-knowledge-base`, 2026-11-23)

- [x] Source docs copied from `00-general-contexts/nexova/` into `docs/company-knowledge-base/` (4 files)
- [x] `data/process/rag.py`: `setup()` + `embed()`; Qdrant collection `nexova_knowledge`, 15 chunks
      (service-lines 4, pricing-model 3, hiring-process-sla 4, objection-handling 4), deterministic uuid5 ids
- [x] `data/pipelines/rag.py`: `retrieve()` (min_score 0.30), `generate_answer()`, `query()`; salesperson
      system prompt with the BRIEFING rules (no discount below 22%, averages not guarantees, competitor transparency)
- [x] `POST /knowledge/query` (`services/api/app/knowledge/router.py`): returns `{answer}` only
- [x] Backoffice `/knowledge` "Sales Assistant" page with loading and error states
- [x] `tests/pipelines/test_rag.py` (16 tests, Qdrant + LLM mocked); Recall@3 = 13/14 = 93% (`data/eval/`)
- [x] `docs/rag/rag-design.md`: process, chunking strategy, embedding practices, min_score tuning
- Decision: models come from the 4Geeks LLM gateway (`https://llm.4geeks.ai/v1`): embeddings
  `pplx-embed-v1-0.6b` (1024-d), generation `deepseek-v4-flash`. Use model ids WITHOUT the `litellm/`
  prefix the dashboard shows (`GET /v1/models` lists the real ones); `glm-5.3-flash` is listed but rejected.
  Student LLM keys expire (the first one expired after ~1 month): regenerate on the 4Geeks profile page.
- Decision: chunk by blank-line semantic units (the docs have no `##` headings), never mid-unit.
- Gotcha: `fastembed`/`onnxruntime` has no wheels for Intel macOS; don't add local embedding models here.
- Known weakness: "can we hire only one service line?" misses the short "contracted independently" chunk.

## Support agent Part 1 — LangGraph (`feature/langgraph-agent-base`, 2026-11-23)

- [x] `services/agent/`: `state.py` (question, context, answer, error, trace_steps — no chat history),
      `nodes.py` (receive_question, retrieve, generate, no_context), `graph.py` (conditional edges,
      compiled at import with a MemorySaver checkpointer), `tracing.py` (JSONL trace store)
- [x] Nodes reuse `data/pipelines/rag.py`: `retrieve()` in its node, `generate_answer()` in another;
      the monolithic `query()` is never called (a test fails if it is)
- [x] `POST /agent/query` → `{answer, trace_id}`; `GET /agent/traces[/{id}]` to query traces
      (`services/api/app/agent/router.py`, imports the compiled graph so a broken graph stops startup)
- [x] Evals on recorded traces (`tests/pipelines/test_agent_evals.py`, fixtures from
      `uv run python -m services.agent.record_eval_traces`) + graph unit tests (`test_agent_graph.py`)
- Decision: when nothing clears min_score the graph routes to `no_context`, a fixed honest answer with no
  model call, so it can't invent Nexova facts.
- Traces: `data/agent_traces/runs.jsonl` locally (gitignored); `AGENT_TRACE_PATH` in Docker, since data/
  is mounted read-only there.

## Support agent Part 2 — ticket tool (`feature/langgraph-external-tools`, 2026-11-23)

- [x] `services/agent/tools.py`: typed `TicketLookupInput` / `TicketLookupOutput`, `lookup_ticket()` reading the
      real incident manager in-process (`app/incidents/service.py` read functions: `get_incident_by_id`,
      `list_incidents`). Read-only (a test fails on any write reference). 4 s timeout (`TICKET_TOOL_TIMEOUT_S`).
- [x] New nodes: `route_intent` (rag / ticket_tool / both from the question text), `lookup_ticket`,
      `handle_tool_failure` (honest not-found / timeout / error text), `synthesize_answer` (ticket facts copied
      from the tool, never generated; policy part from `generate_answer()`).
- [x] Traces now record `route`, `route_rationale`, `sources_used` (ordered) and `tool_outcome`.
- [x] Evals: ticket → tool only, policy → RAG only, missing ticket → fallback, mixed → tool then RAG
      (`test_agent_evals.py`), plus `test_agent_tools.py` (contract, timeout, routing table, read-only).
- Decision: in-process instead of HTTP: the agent runs inside the same FastAPI app, and the HTTP routes need a
  user JWT. The service layer is exactly what `GET /api/incidents[/{id}]` call. No auth needed in-process.
- Decision: rule-based router (ticket number / ticket words / policy keywords) so routing is deterministic,
  explainable in the trace and testable without a model.
- Stretch (inventory) skipped: inventory lives on Supabase, which is currently unreachable.
- Record fixtures with services/api's env: `uv run --project services/api python -m services.agent.record_eval_traces`.
- Fix: for `both`, retrieve searches only the policy clause (`rag_question`), not the ticket wording, which had
  diluted similarity below min_score so the policy half came back empty (caught by the mixed-question eval).
- Known retrieval gap: "what does our replacement guarantee cover?" scores just under min_score 0.30 with
  pplx-embed, so the agent honestly says the knowledge base has nothing (no invention). Mixed-question eval uses
  the shortlist question instead; threshold deliberately not lowered.
