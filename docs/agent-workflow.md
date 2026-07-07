# Agent Workflow

This document is the single source of truth for how Claude, Codex, and humans
work on FlatFeed without stepping on each other. `CLAUDE.md` and `AGENTS.md` are
thin entry points that link here; the actual rules live below. It does not
restate the design and content rules — those stay in
`DESIGN_CONTENT_SYSTEM.md`, which this workflow references.

## Source Of Truth

Project context lives in repository files, not in chat threads or local notes:

- `README.md` for human onboarding, setup, run, and eval commands;
- `DESIGN_CONTENT_SYSTEM.md` for UI, layout, component, copy, terminology,
  accessibility, evidence, and case-study rules. It is the cross-repo normative
  standard (shared convention with the sibling Opsqora landing); start from its
  §0 "Quick Start for Agents" to find the touched surface and its invariants;
- `docs/PROJECT_CONTEXT.md` for durable product semantics (filters, listing
  card, parsing rules, AI QA boundaries, data model, reliability decisions);
- `CLAUDE.md` for Claude entry context;
- `AGENTS.md` for Codex and other coding agents.

For behavior, code constants win over any document: `flatfeed/wbs_rules.py`
(WBS semantics), `flatfeed/matching.py` (card format), `flatfeed/ai_qa.py`
(prompt version, risk thresholds), `eval/run_eval.py` (metrics).

## Required Response Context

After every user request, state which model and which reasoning power should be
used for the task.

## Project Guardrails

- FlatFeed is a portfolio prototype: a Telegram bot and Streamlit dashboard that
  collect Berlin WBS listings and match them to user filters. Preserve this
  Phase 1 scope unless the user explicitly asks for a new phase.
- Keep the demo synthetic and deterministic. Listings come from the synthetic
  catalog in `synthetic/` through the synthetic source adapter; SQLite
  (`flatfeed/db/`) accelerates selection and preserves history. There is no real
  scraping, no network geocoding (Photon/Google Maps), no image reuploading, and
  no live-source capability claims — multi-source collection and source health
  are exercised through the synthetic adapter only.
- Preserve both public surfaces: the Telegram/dashboard prototype and the case
  study at `docs/case-study.html`.
- Deterministic parsing and matching own all user-facing decisions and fail
  closed on unknown values. AI QA never mutates listings, matching, or cards; it
  is admin-only, budgeted, versioned, and non-mutating. No backend beyond
  SQLite, no auth, no billing, no external model calls beyond optional admin-only
  AI QA unless explicitly requested — treat any such move as a new phase and
  document it first.
- Synthetic ground truth and case tags never enter parser/AI QA prompts, listing
  text, or URLs — they are eval-only metadata.
- WBS remains a legitimate domain term: keep WBS parsing, labels, and matching
  semantics; never translate it away.
- `LOCAL_CONTEXT.md` is local-only (git-ignored). Operational/server/bot details
  from it MUST NOT appear on any committed or public surface.

## Build And Verification

Choose checks by the riskiest touched surface using the **verification matrix in
`DESIGN_CONTENT_SYSTEM.md` §31** — do not default to the heaviest checks for a
documentation-only edit, and run broader checks when a change crosses surfaces.

Baseline commands (from the README "Development Checks"):

```bash
PYTHONPYCACHEPREFIX=/tmp/flatfeed-pycache .venv/bin/python -m unittest discover -s tests
PYTHONPYCACHEPREFIX=/tmp/flatfeed-pycache .venv/bin/python -m eval.run_eval
git diff --check
```

If you skip a heavier check that the matrix would run, say why in your handoff.

## Working Style

- Make focused, reviewable changes; avoid broad refactors when a focused change
  solves the task.
- Prefer existing UI, data, and naming patterns over introducing new
  abstractions or tooling; when the standard is silent, follow the closest
  approved pattern in `DESIGN_CONTENT_SYSTEM.md` §28.
- Propagate copy and eval-number changes across bot, dashboard, tests, and docs
  together — no surface drifts out of sync (`DESIGN_CONTENT_SYSTEM.md` §27).
- Keep durable context in `docs/` (or `DESIGN_CONTENT_SYSTEM.md`) instead of
  duplicating long context in `CLAUDE.md`/`AGENTS.md`.
- Record any new/changed rule through Change Governance
  (`DESIGN_CONTENT_SYSTEM.md` §34), and update the relevant `docs/` file when
  behavior, scope, or agent expectations change.

## Avoiding Agent Conflicts

- Prefer one active agent per branch; give Claude and Codex separate branches or
  clearly separate tasks.
- Check `git status --short` before significant edits.
- Do not revert or overwrite uncommitted changes from another agent or the user.
- If a requested change appears to conflict with `DESIGN_CONTENT_SYSTEM.md`,
  pause and call out the conflict before editing. When two rules pull in
  different directions, apply the conflict hierarchy in §4 (factual integrity and
  trust boundaries over consistency, consistency over visual preference).

## Done Definition

A change is done when:

- the requested behavior or documentation exists;
- the checks required by the §31 matrix pass — tests, the eval, and
  `git diff --check` are green;
- both public surfaces (prototype and `docs/case-study.html`) are still
  accounted for;
- evidence labels, terminology, and ownership language stay meaning-identical
  across every surface the change touches, and nothing from `LOCAL_CONTEXT.md`
  leaked onto a committed surface;
- any changed scope, architecture, or workflow expectation is documented in
  `docs/`.
