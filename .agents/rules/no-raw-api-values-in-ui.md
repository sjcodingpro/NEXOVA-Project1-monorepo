# Rule: never render raw API enum values in the UI

**Scope:** file-pattern based — applies to any component, page, or
template file under `uis/**` that displays data sourced from an API
whose fields are constrained enums (e.g. `status`, `stage`, or any
similarly coded field introduced later).

## The rule

Raw API enum values (e.g. `in_progress`, `personal_interview`,
`received`) must never be rendered directly in the UI, in any app
under `uis/`. Every such value must be passed through an explicit
label map before display.

## Why

This was an explicit, evaluated requirement on the Talent Pipeline
Tracker milestone: "Raw API values must never be visible in the
interface. Always use the labels from this table." It is treated as
a correctness requirement, not a stylistic preference, because these
codes are internal API implementation details — end users (Nexova's
People & Talent team, candidates, etc.) should only ever see
Nexova's actual business terminology.

## How to apply it

- Define the mapping once, in a single file per app (see
  `uis/talent-pipeline-tracker/lib/labels.ts` for the reference
  pattern: `STATUS_LABELS`, `STAGE_LABELS`, plus derived
  `STATUS_OPTIONS`/`STAGE_OPTIONS` arrays for building `<select>`
  inputs).
- Every place that renders the value — tables, badges, dropdowns,
  detail views — reads through that map. Never inline a raw value in
  JSX/HTML, and never leave a raw value unmapped "temporarily."
- If a new coded/enum field is introduced (new app, new API), add its
  label map to that app's equivalent of `lib/labels.ts` before
  wiring up any UI that displays it — do not ship the UI first and
  add labels later.

## Verification

Before committing any change that touches a file matching `uis/**`
and displays API-sourced data, grep the diff for the raw enum values
you know exist (e.g. `in_progress`, `personal_interview`) — none
should appear inside JSX/HTML output, only inside the label-mapping
file itself.
