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
