# Skill: Scaffold a new uis/ app

## Objective

Set up a new frontend application under `uis/<app-name>/` that follows
this monorepo's established conventions, so it is immediately
consistent with the other apps in `uis/` (documented, buildable,
runnable, with environment variables handled correctly) without a
developer having to manually replicate the pattern each time.

This is a recurring task: it has already been performed twice in this
repo (moving `uis/website` into convention, and building
`uis/talent-pipeline-tracker` from scratch) and will recur for every
future app added under `uis/`.

## Inputs (must be provided before running this skill)

- `app_name` — the folder name under `uis/` (e.g. `backoffice`)
- `purpose` — one or two sentences describing what the app does and
  which real Nexova problem it solves (must be grounded in
  `CONTEXT.md` / `memory-bank/projectbrief.md`, not generic)
- `stack` — the framework/tooling choice (e.g. "Next.js App Router +
  TypeScript", or "static HTML + Tailwind" as with `uis/website`)
- `needs_env_vars` — yes/no, and if yes, which variables (e.g. an API
  base URL)

## What this skill does

1. Creates `uis/<app_name>/` and initializes the chosen stack inside
   it (e.g. `npx create-next-app@latest .` for a Next.js app).
2. If `needs_env_vars` is yes: creates `.env.local` (gitignored) with
   real values for local development, and a committed `.env.example`
   documenting the same variable names with placeholder/example
   values.
3. Confirms `.gitignore` at the app level (or inherited from repo
   root) actually excludes `.env.local`, `node_modules`, and any
   build output directory — does not assume, checks.
4. Writes `uis/<app_name>/README.md` documenting: objective (from
   `purpose`), technology used (from `stack`), and how to run it
   locally — per the convention already established in
   `uis/website/README.md` and `uis/talent-pipeline-tracker/README.md`.
5. Runs the app's install and dev/build commands to confirm it starts
   without errors.
6. Updates `memory-bank/progress.md` and, if relevant,
   `memory-bank/techContext.md` to record the new app's existence and
   any architectural decisions made while scaffolding it.

## Acceptance criteria (all must be true — unverifiable claims don't count)

- [ ] `uis/<app_name>/` exists and contains a working app for the
      chosen stack (e.g. `package.json` + entry point).
- [ ] `uis/<app_name>/README.md` exists and documents objective,
      stack, and local run instructions — not boilerplate scaffold
      text.
- [ ] If the app needs environment variables: `.env.example` exists
      and is committed; `.env.local` (if created) does **not** appear
      in `git status` as trackable.
- [ ] Running the app's install + dev command completes with no
      errors, and the app is reachable at the port/URL it reports.
- [ ] `memory-bank/progress.md` reflects the new app's existence
      after this skill runs — checked by diffing that file before and
      after.
- [ ] No files outside `uis/<app_name>/` and `memory-bank/` were
      modified as a side effect (verified via `git status` /
      `git diff --stat` before committing).
