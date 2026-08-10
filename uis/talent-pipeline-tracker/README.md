# Talent Pipeline Tracker — Nexova People & Talent

Internal recruiting dashboard for Nexova's People & Talent team. Replaces
the shared spreadsheet previously used to track candidates, notes, and
interview stages across active searches (e.g. the Executive Assistant
search at Nexova's Valencia headquarters).

Built with Next.js (App Router), React, and TypeScript against the
Talent Tracker API. No external state management — component-level hooks
only, per this milestone's constraints.

## What it does

- Candidate list (/) — all candidates with position, status, and stage
  at a glance. Filter by status/stage and search by name or email, all
  synced to the URL so filtered views are shareable and survive a refresh.
- Candidate detail (/candidates/[id]) — full candidate record,
  status/stage updates, and internal notes (add/delete).
- Register candidate (/candidates/new) and edit candidate
  (/candidates/[id]/edit) — validated forms with success/error feedback.

Raw API values (in_progress, personal_interview, etc.) are never shown
directly — see lib/labels.ts for the mapping to Nexova's UI labels.

## Getting started

    npm install
    cp .env.example .env.local
    npm run dev

Open http://localhost:3000

## Structure

    app/                     routes (list, detail, edit, new)
    components/               presentational pieces (filters, table, forms, states)
    hooks/useRecordsFilters   URL-synced status/stage/search state
    lib/api.ts                typed fetch wrapper for the Talent Tracker API
    lib/labels.ts              status/stage to Nexova UI label maps
    types/candidate.ts         TypeScript types for all API shapes

## Environment

| Variable | Purpose |
|---|---|
| NEXT_PUBLIC_API_URL | Base URL of the Talent Tracker API, see .env.example |
