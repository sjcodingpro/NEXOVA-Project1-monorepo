# Project Brief — Nexova

## The company

Nexova is a human resources consulting and talent acquisition firm founded
in 2011, headquartered in Valencia, Spain, with an expansion office in
Miami, Florida. Approximately 120 employees, ~$8M annual revenue. Clients
are primarily mid-sized companies in technology, retail, and financial
services.

Three business lines:
1. Executive and mid-management headhunting
2. Customer support team outsourcing for technology companies
3. Corporate training in soft skills and leadership

## What this monorepo is building

This monorepo hosts Nexova's internal engineering build-out across several
workstreams, each tied to a specific real business pain point:

### 1. Public website and lead capture (uis/website)

Owner: Carmen Ruiz, Head of Marketing.
Problem: Nexova's 2019 website is outdated, slow, and not accessible.
There is no structured way to capture candidate leads — interested
professionals currently email info@nexova.com with no structure, which
is chaos for the marketing team to process.
Solution: a modern landing page presenting Nexova's services, plus a
structured talent registration form (contact details, experience,
sector of interest, English level, availability) replacing the email
free-for-all.

### 2. Internal candidate pipeline (uis/talent-pipeline-tracker)

Owner: Elena Vargas, L&D Manager, escalated via Sergio Molina (CTO).
Problem: Nexova's own internal hiring (e.g. the Executive Assistant
search at the Valencia HQ) was tracked in a shared spreadsheet — leading
to duplicated candidate entries and stale statuses. This is a real,
embarrassing operational gap for a company whose actual business is
recruiting.
Solution: a candidate pipeline UI against the shared Talent Tracker API
— list/filter/search candidates, update status/stage, manage internal
notes, register and edit candidates.

### 3. Internal backoffice (uis/backoffice)

The umbrella internal application for Nexova's operational tooling —
starting minimal (entry view + one piece of real company data visible),
intended to grow into the home for auth, people management, and
operations tooling over time. Not a consolidation of existing apps
(the talent pipeline tracker remains independent for now) — this is a
fresh, separate shell.

### 4. Agent infrastructure (this milestone)

Problem, per the engineering tech lead: the repo has no persistent,
structured context for coding agents. Every new agent session risks
re-learning (or getting wrong) the company's identity, technical
decisions, and rules from scratch, which costs real engineering time
to correct.
Solution: a memory bank (this folder), an AGENTS.md defining mandatory
agent workflow, scoped rules under .agents/rules/, and at least one
verifiable, reusable agent skill under .agents/skills/.

## Why this matters

Nexova is, itself, a recruiting company — its own hiring process was run
on a spreadsheet until recently, and its public-facing lead capture was
an unstructured inbox. The throughline across every workstream here is
replacing ad hoc, error-prone manual processes (spreadsheets, email
threads, tribal knowledge) with structured, reliable systems — for
external candidates, internal recruiters, and now for the coding agents
building all of it.
