# backoffice

Internal operations dashboard for Nexova.

## Objective

The umbrella application for Nexova's internal tooling — starting as a
minimal entry shell (welcome view with a company snapshot) and intended
to grow into the home for people management, recruiting operations
support, and other internal capabilities over time. This is a separate
app from `uis/talent-pipeline-tracker`, not a replacement for it.

## Technology

Next.js (App Router) + React + TypeScript + Tailwind CSS. No external
state management library, consistent with the other Next.js app in
this monorepo.

## Running locally

    npm install
    npm run dev

Open http://localhost:3000. No environment variables are required yet —
the entry view renders static company data sourced from CONTEXT.md.
