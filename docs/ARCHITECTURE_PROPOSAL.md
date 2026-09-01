# Backend Architecture Proposal — Nexova

Author: Engineering
Status: Draft for CTO review, pre-implementation
Scope: services/ — the centralized FastAPI backend for Nexova

## 1. Where this fits

Over the last four milestones we've built three independent frontends
against Nexova's real business context:

- uis/website — public site + talent registration form (currently
  simulates submission; no persistence layer yet)
- uis/talent-pipeline-tracker — internal candidate pipeline UI,
  currently backed by a shared external sandbox API
  (playground.4geeks.com/tracker/api/v1), not by anything Nexova owns
- uis/backoffice — internal operations shell, currently static data

None of these have a real, Nexova-owned backend yet. This document
proposes how services/ — the "one centralized FastAPI backend for the
whole company" called for in this monorepo's own conventions — should
be structured before any endpoint code is written.

## 2. Chosen architectural pattern: domain-driven modular monolith

Pattern: a single FastAPI application, internally organized by
business domain (feature-based structure), not a set of microservices
and not a classic MVC template-rendering app.

Why this fits Nexova specifically, not architecture in the abstract:

- Company size and team size don't justify microservices. Nexova is
  ~120 employees, three business lines, $8M revenue — a mid-size
  company with, at this stage, a single engineering team building
  everything. Microservices add operational cost (service discovery,
  distributed tracing, inter-service auth, multiple deploy pipelines)
  that pays off with multiple independent teams and genuinely
  independent scaling needs, neither of which exists here yet.
  Adopting microservices now would be solving a scale problem Nexova
  doesn't have.
- MVC (template-rendered) doesn't fit because there is no
  server-rendered view layer. All three frontends
  (uis/website, uis/talent-pipeline-tracker, uis/backoffice) are
  separate deployable clients that consume an API over HTTP — two are
  already Next.js apps, and the website is static HTML. A backend
  built around server-rendered views would be architecture for a UI
  paradigm Nexova has already moved past.
- Serverless doesn't fit Nexova's workload shape. Nexova's workloads
  (candidate applications, pipeline updates, internal dashboards) are
  steady, low-to-moderate-traffic, transactional CRUD over a
  relational-shaped domain — not bursty, event-driven, or
  embarrassingly parallel work that serverless functions suit. A
  long-running FastAPI process is simpler to reason about and cheaper
  to operate at this scale.
- The monorepo's own services/README.md already recommends this exact
  shape: one main FastAPI app with routers/modules per domain, avoid
  splitting into many microservices early. This proposal follows that
  existing convention rather than introducing a new one.
- This matches how production FastAPI monoliths are actually
  structured once they outgrow a handful of endpoints. The
  feature-based, domain-driven layout described in the
  zhanymkanov/fastapi-best-practices repository on GitHub (also
  summarized by Auth0's FastAPI best-practices engineering blog post)
  is the standard answer to exactly Nexova's shape: many business
  domains and modules, where a file-type layout (all routers
  together, all models together) breaks down into giant, tangled
  directories. We are adopting that structure, not inventing our own.

## 3. Folder and module structure

See the tree below. Each top-level package under app/ corresponds to
one business capability Nexova's frontends actually need (candidates,
leads, notes, content, auth), not to a technical layer (routers/,
models/, schemas/ globally). Each domain owns its own router, schema,
model, and service logic. Cross-cutting infrastructure (settings,
CORS, DB session, shared response shapes) lives in core/, db/, and
shared/, not duplicated per domain.

This directly follows the "package by feature, not by file type"
principle from the research above. Nexova already has three
non-trivial domains (candidates, leads, content) from day one, so a
file-type layout would already be under strain at launch.
    services/
      api/
        app/
          main.py                (FastAPI app instantiation, router registration)
          core/
            config.py             (Settings via pydantic settings: env vars)
            cors.py                (CORS origin configuration)
            security.py            (Auth/token handling for backoffice login, later)
          db/
            session.py             (DB session/connection setup)
          candidates/
            router.py              (/candidates endpoints)
            schemas.py              (Pydantic request/response models)
            models.py               (ORM models)
            service.py               (status/stage transitions, business logic)
            exceptions.py             (domain-specific exceptions)
          leads/
            router.py              (/leads endpoints -- talent registration intake)
            schemas.py
            models.py
            service.py
          notes/
            router.py               (/candidates/{id}/notes)
            schemas.py
            models.py
          content/
            router.py               (business-line/service descriptions for
                                       uis/website and uis/backoffice)
            schemas.py
            models.py
          auth/
            router.py               (backoffice staff login -- future)
            schemas.py
            models.py
          shared/
            pagination.py            (shared {data, total, page, limit}
                                        response envelope, matching the shape
                                        already used by the external Talent
                                        Tracker API)
        tests/
          candidates/
          leads/
          notes/
          content/
        pyproject.toml or requirements.txt
        .env.example

## 4. Routes and domains

No code — described at the level of what routes exist and why they
are grouped together:

- /leads — POST /leads (talent registration form submission from
  uis/website), GET /leads (marketing/recruiting review). Separate
  from /candidates because a lead is raw, unqualified interest;
  promoting a lead into the active candidate pipeline is a deliberate
  business action, not automatic.
- /candidates — GET /candidates, GET /candidates/{id},
  POST /candidates, PUT /candidates/{id}, PATCH /candidates/{id}
  (status/stage). This is the domain uis/talent-pipeline-tracker
  should eventually consume instead of the external sandbox API (see
  Section 6).
- /candidates/{id}/notes — GET, POST, DELETE. Nested under candidates
  in the URL because notes have no independent meaning, but
  implemented as their own module so note-specific logic doesn't
  bloat the candidates service file.
- /content — GET /content/services (the three business lines'
  descriptions), used by both uis/website and uis/backoffice so copy
  changes don't require a frontend redeploy.
- /auth — staff login for uis/backoffice (not required by the current
  milestone's minimal entry view, but reserved now so it isn't
  awkwardly retrofitted into another domain later).

All routes versioned under /api/v1, matching the convention already
established by the external Talent Tracker API (/tracker/api/v1/...)
that uis/talent-pipeline-tracker already consumes — keeping the same
shape reduces cognitive load when that app eventually switches data
sources.

## 5. Frontend/backend separation considerations

Nexova's frontend and backend are already, structurally, separate
systems — three independent frontend apps under uis/, each with its
own package.json and its own deploy target, none of them
server-rendering from this backend. This proposal keeps that shape
rather than merging them:

- API communication: each frontend talks to the backend over HTTP via
  a single configured base URL, following the pattern already used in
  uis/talent-pipeline-tracker (NEXT_PUBLIC_API_URL, read once in
  lib/api.ts, never hardcoded per call site).
- Environment variables: the backend's own secrets (DB credentials,
  future auth signing keys) live in the backend's own .env and are
  never exposed with a NEXT_PUBLIC_ (or equivalent) prefix — those
  prefixes make a variable visible in client-side JS bundles by
  design, so this is a real risk, not a style rule. Each app keeps its
  own .env.example documenting only what it needs.
- CORS: the backend must explicitly allow-list the actual origins of
  uis/website, uis/talent-pipeline-tracker, and uis/backoffice (their
  deployed URLs) rather than a wildcard, since the backend will handle
  candidate PII (names, emails, phone numbers) and should not accept
  cross-origin requests from arbitrary sites.

## 6. Risks and points of attention

1. Two sources of truth for candidate data. Today,
   uis/talent-pipeline-tracker reads candidates from a shared, generic
   external sandbox API, not from anything Nexova owns. If the team
   starts this backend's /candidates domain without an explicit
   decision and migration plan for switching the tracker frontend
   over to it, we risk running two parallel, disagreeing "sources of
   truth" for candidate status indefinitely. This should be an
   explicit, scheduled migration, not something that happens silently
   or gets forgotten.
2. Domain boundaries eroding under time pressure. The whole
   justification for this structure is that each domain
   (candidates/leads/notes/content) stays self-contained. The
   realistic risk is a developer, under a deadline, importing
   candidates.service directly from inside leads/router.py to
   "quickly" promote a lead, instead of going through a proper
   cross-domain interface. Once that happens once, the domain
   boundaries stop meaning anything and the codebase reverts to the
   tangled, file-type-style mess this structure was chosen to avoid.
3. CORS/environment misconfiguration across three independently
   deployed frontends. With three separate uis/* apps each pointing
   at the backend via their own environment variable, a missed origin
   in the CORS allow-list or a stale API URL in one app's
   .env.example will surface as a confusing runtime failure in
   production, not a build-time error — this is worth a documented
   deployment checklist before the first real deploy, not something
   to debug ad hoc when it breaks.
4. /leads vs /candidates conflation. Because both domains describe "a
   person interested in a job," there is a real risk a developer
   treats them as the same thing and merges the domains for
   convenience. This would remove the deliberate business distinction
   Carmen Ruiz's team needs (raw inbound interest vs. an actively
   managed pipeline candidate) and should be actively resisted during
   implementation, not just documented here and forgotten.
