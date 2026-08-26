# Tech Context — Nexova Monorepo

## Repo shape

This is a single monorepo housing multiple independent applications under
`uis/`, following the folder conventions in the root README.md:

- `uis/website/` — public marketing site + talent registration form
- `uis/talent-pipeline-tracker/` — internal candidate pipeline
- `uis/backoffice/` — internal operations shell (new, this milestone)
- `services/` — shared backend API surface (not yet populated)
- `agents/`, `skills/`, `mcps/` — product-code AI agents/skills/tool
  servers for later modules (distinct from `.agents/`, see below)
- `data/` — raw/pipelines/process/eval datasets (not yet populated)
- `memory-bank/`, `.agents/`, `AGENTS.md` — agent configuration (this
  milestone)

Each app under `uis/` is independent: its own `package.json`, its own
stack, its own README. There is no shared build system across them.

## uis/website

- Stack: static HTML + Tailwind CSS (CLI build) + vanilla JS for form
  validation. No frontend framework.
- Build: `npm run build` compiles `src/input.css` → `styles.css`.
  `npm run dev` runs the Tailwind watcher and a static file server
  (`http-server`) concurrently on port 3000.
- Deploy: `npm run build:vercel` copies static output into `public/`;
  `vercel.json` sets `outputDirectory: public`. If deployed via Vercel,
  the project's Root Directory setting must point at `uis/website`
  (this app was moved from repo root during this milestone).
- Two languages: English (`index.html`, `application.html`) and Spanish
  (`index.es.html`, `application.es.html`) as separate static pages —
  no i18n framework, no shared templating/includes system. Header/footer
  markup is duplicated across the four HTML files (acceptable for the
  current scope; would need a templating layer or SSG to deduplicate).
- Required Schema.org `Organization` JSON-LD on the landing page (already
  present in `index.html`).

## uis/talent-pipeline-tracker

- Stack: Next.js (App Router) + React + TypeScript. No external state
  management library — component-level `useState`/`useReducer` and
  plain hooks only (explicit constraint for that milestone).
- Talks to the shared Talent Tracker API
  (`NEXT_PUBLIC_API_URL`, see its own `.env.example`).
- Key architectural decisions:
  - `lib/api.ts` — single thin fetch wrapper; all endpoints typed,
    errors surfaced from FastAPI's `{ detail: [...] }` validation shape.
  - `lib/labels.ts` — raw API enum values (`status`, `stage`) are never
    rendered directly; always mapped through label constants here.
  - `GET /records` and `GET /records/:id/notes` both return paginated
    wrapper objects (`{ data, ... }`), not bare arrays — a real gotcha
    hit during that build, now reflected in the types
    (`RecordsListResponse`, `NotesListResponse`).
  - Filters/search live in the URL via `useSearchParams`, not local-only
    state, so filtered views are shareable/persist on refresh.

## uis/backoffice

- New in this milestone. Recommended stack: Next.js + TypeScript, for
  consistency with the tracker (same monorepo, same conventions), unless
  a decision is made otherwise when it's actually built out.
- Scope for this milestone: `/` entry view with its own layout (distinct
  from `uis/website`'s layout) and at least one real piece of Nexova
  data from `CONTEXT.md` visible on screen — not just console output.
- Intended long-term direction (per `uis/README.md`): the umbrella for
  future internal tooling (auth, people management, operations). Not
  consolidating `talent-pipeline-tracker` into it as part of this
  milestone — that would be a separate, deliberate future change.

## Agent configuration (this milestone)

- `memory-bank/` — persistent context read by any coding agent at the
  start of a session (this file, `projectbrief.md`, `progress.md`).
- `AGENTS.md` (repo root) — defines the mandatory pre-commit workflow
  and files the agent must not touch without explicit confirmation.
- `.agents/rules/` — scoped development rules (always-active,
  file-pattern-based, or agent-requested).
- `.agents/skills/<skill>/SKILL.md` — reusable, verifiable agent
  skills with documented inputs/outputs and explicit acceptance
  criteria.
- Important distinction: `.agents/` configures how the coding tool
  behaves in this repo. `/agents` and `/skills` at repo root are
  product code — AI agents and skills built for Nexova's own use cases
  in later modules. Do not conflate the two.

## Constraints worth remembering

- No repo-wide build system or shared tooling across `uis/*` apps —
  each is independently buildable and runnable.
- `.env.local` files are gitignored everywhere; `.env.example` is the
  committed contract for required environment variables.
- Company terminology/framing must be reflected in UI copy across every
  app — raw API values or generic placeholder text is treated as a
  rejection-worthy gap in every milestone so far.
