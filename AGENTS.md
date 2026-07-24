# FlatFeed Agent Instructions

This file is the shared entry point for Codex and other coding agents.

## Required Context

Before changing code or docs, read:

- `README.md`
- `DESIGN_CONTENT_SYSTEM.md` — normative design, content, component,
  terminology, accessibility, and case-study system
- `docs/PROJECT_CONTEXT.md` — product semantics (filters, listing card, parsing,
  AI QA boundaries, data model)
- `docs/CURRENT_STATUS.md` — changing experiment status, consumed evidence,
  current decision, and recommended next step
- `docs/agent-workflow.md` — the single rulebook: guardrails, Phase 1
  boundaries, build/verify, working style, and collaboration rules

## Rules

All working rules — required response context, project guardrails, Phase 1
boundaries, build and verification steps, working style, conflict avoidance, and
the done definition — live in `docs/agent-workflow.md`. Read it before changing
code or docs; it is the single source of truth and is not duplicated here.
