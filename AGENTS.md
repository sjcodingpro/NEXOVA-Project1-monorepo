# AGENTS.md — Nexova Monorepo

This file defines how any coding agent (Claude Code, Cursor, Windsurf,
etc.) must operate in this repository. It is read automatically at the
start of every agent session working in this repo.

## 1. Required reading at session start

Before touching any code, read, in this order:

1. `CONTEXT.md` — Nexova's company briefing (source of truth for all
   business facts, terminology, and constraints)
2. `memory-bank/projectbrief.md` — business context and why each part
   of this repo exists
3. `memory-bank/techContext.md` — stacks, architectural decisions,
   and per-app constraints
4. `memory-bank/progress.md` — current state, in-progress work, and
   decisions already made

If a task touches a specific app under `uis/`, also read that app's own
`README.md` before making changes.

## 2. Mandatory workflow before every commit

These steps are ordered and none may be skipped:

1. **Re-read `memory-bank/progress.md`** to confirm the change you're
   about to make isn't already done, already decided against, or
   conflicting with an open item logged there.
2. **Check `.agents/rules/`** for any rule whose scope matches the
   files you're about to change, and follow it. If a rule and a direct
   instruction conflict, stop and ask rather than silently picking one.
3. **Make the change**, scoped to what was asked — do not bundle
   unrelated refactors or touch apps outside the current task's scope
   (see Section 3).
4. **Verify the change**: for any app with a build/lint/test command
   (e.g. `npm run build`, `npx eslint .` inside that app's folder), run
   it and confirm it passes before considering the change done. For
   static content changes (e.g. `uis/website`), manually verify the
   affected page still renders correctly.
5. **Update `memory-bank/progress.md`** if the change affects overall
   project state — completed a checklist item, made a new decision,
   discovered a new constraint, or opened a new question. A memory
   bank that isn't updated stops being useful within days.
6. **Commit** with a message that states what changed and why,
   referencing the relevant workstream (e.g. `uis/website`,
   `uis/backoffice`, agent infrastructure).

## 3. Do not modify without explicit developer confirmation

- `CONTEXT.md` / `CONTEXT.es.md` — the company briefing is the source
  of truth for every other decision in this repo. If it appears wrong
  or outdated, flag it and ask; do not edit it unilaterally.
- `uis/talent-pipeline-tracker/` — already built, tested, and
  delivered as its own milestone. Any change here should be a
  deliberate, separate task, not a side effect of unrelated work.
- Any `.env.local` file, anywhere in the repo — these are gitignored
  and contain machine-specific configuration; never create, edit, or
  attempt to commit one.
- `package-lock.json` files — regenerate via `npm install`, never
  hand-edit.
- `memory-bank/` files should be *updated*, not deleted or rewritten
  wholesale, unless a developer explicitly asks for a rewrite.
- Git history (`rebase`, `force-push`, amending already-pushed
  commits) — never rewrite shared history without explicit
  instruction.

## 4. Repo-wide conventions

- Every app under `uis/` is independent — its own dependencies, its
  own build, no shared tooling assumed across apps.
- `.agents/` (this repo's coding-agent configuration: rules, skills)
  is not the same as the root-level `/agents` and `/skills` folders
  (product code — AI agents and skills built for Nexova's own
  business use cases). Do not confuse the two when reading or writing
  either.
- UI copy, labels, and terminology in every app must reflect Nexova's
  actual context (`CONTEXT.md`) — generic placeholder content is
  treated as incomplete work, not a stylistic choice.
