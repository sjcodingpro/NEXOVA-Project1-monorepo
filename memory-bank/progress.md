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

## In progress (this milestone — agent infrastructure)

- [x] `CONTEXT.md` confirmed as the real Nexova briefing (not the
      template placeholder) — no action needed, already correct.
- [x] `memory-bank/projectbrief.md` — business context
- [x] `memory-bank/techContext.md` — technical context
- [ ] `memory-bank/progress.md` — this file, keep updating as work
      continues
- [ ] `AGENTS.md` at repo root — mandatory read list, ≥4-step pre-commit
      workflow, do-not-touch list
- [ ] `.agents/rules/` — at least one scoped rule
- [ ] `.agents/skills/<skill>/SKILL.md` — at least one verifiable skill
- [ ] `uis/backoffice/` — new app, own layout, `/` entry view, at least
      one real piece of Nexova data visible on screen
- [ ] Run the AGENTS.md delivery workflow before final commit
- [ ] Open PR from `feature/agent-memory-bank` → `main` with required
      screenshots + AGENTS.md link

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
