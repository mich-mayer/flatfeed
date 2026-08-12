# FlatFeed Current Status

**Last verified:** 2026-08-11
**Purpose:** short handoff for a new human or AI work session. Read this after
`AGENTS.md` / `CLAUDE.md` and before proposing the next experiment.

This file records changing project state. Stable product rules belong in
`docs/PROJECT_CONTEXT.md`; working rules belong in `docs/agent-workflow.md`;
the full experiment history and contracts belong in
`eval/AI_QA_EVAL_PLAN.md`.

## Product State

- FlatFeed is a product-first Telegram prototype for reducing repeated checks
  across Berlin WBS listings with four saved criteria: WBS type, district,
  maximum Kaltmiete, and rooms.
- The implemented demo uses one synthetic source adapter. It does not scrape or
  redistribute real housing-company listings and does not claim live source
  coverage or user outcomes.
- Parsing and matching are deterministic and fail closed on unknown critical
  values.
- The Telegram bot is the working implementation artifact; the case study uses
  captured screens from that product flow and does not link to or invite readers
  to open the bot. Saved-filter
  setup, on-demand `Show matches`, persistent `Filter` / `Show matches`
  actions, individual field editing, reset and data deletion are implemented.
  Background notifications are implemented behind `BOT_BACKGROUND_ENABLED`.
  The Streamlit dashboard, public admin panel, unfiltered catalog browser, and
  mock QA tour remain outside current scope.
- `/start` opens the filter home. A user can save the four criteria and request
  up to three results from the synthetic catalog. Each result is the canonical
  card produced by the deterministic matching, local activity-check, and card
  formatter path; no separate match-reason message is sent.
- `/filter`, `/matches`, `/help`, and `/delete` are public commands. Buttons
  from the retired guided tour redirect to the current saved-filter flow
  without writing filter state themselves.
- The public Telegram product flow makes no model call. Optional runtime AI QA remains
  bounded to direct admin alerts when explicitly enabled; it cannot mutate
  parsed listings, matching, or user-facing cards. No hosted model from the
  offline experiment is integrated into product runtime.

## Final AI QA Evaluation

The accepted synthetic configuration is:

- model: `gpt-5.6-terra`;
- reasoning effort: `high`;
- prompt: `extraction-v1`;
- strict Structured Outputs;
- `max_output_tokens=768`;
- zero retries and no post-run tuning or rescoring.

The model receives only raw listing text and returns exact source quotes for
eight values. Deterministic code compares those values with the parser
snapshot. A mismatch or unreadable value produces one admin-facing outcome:
`review_required`. The model does not decide what users see.

The final dataset was newly generated and frozen before the API run. It
contains 600 synthetic listings: 300 clean and 300 with one planted parser
error. Its inputs have no overlap with 22 prior input artifacts.

| Metric | Result | Gate | Status |
|---|---:|---:|---|
| Parser Error Detection Rate | 300/300, 100.0% | at least 294/300 | Pass |
| False Alert Rate | 0/300, 0.0% | at most 3/300 | Pass |
| Correct Field Detection Rate | 300/300, 100.0% | at least 294/300 | Pass |
| Successful Check Rate | 599/600, 99.8% | at least 597/600 | Pass |

Every field gate passed: WBS 75/75, Kaltmiete 60/60, rooms 50/50,
address/postal code 40/40, district 30/30, floor 25/25, and Warmmiete 20/20.

One clean listing returned an evidence quote that was not present verbatim in
the raw text. Local validation rejected it; the case was not retried and did
not create a false alert. The run cost `$1.412906`.

**Decision:** accept this as the final synthetic feasibility result. Stop
synthetic tuning. Do not integrate the hosted model into product runtime yet;
the portfolio prototype is complete at its intended scope.

The earlier `terra-v1`, `review-v1`, and extraction-development results remain
in `eval/AI_QA_EVAL_PLAN.md` and `eval/AI_QA_FAILURE_ANALYSIS.md` as experiment
history. They are not current public evidence.

## Experiment Boundaries

- The original locked holdout and the new extraction-v1 final dataset are both
  consumed. Do not rerun, tune against, regenerate, or rescore either one.
- Do not rerun the consumed calibration or frozen-validation datasets as a new
  acceptance attempt.
- Do not present balanced synthetic challenge-set metrics as production
  precision or natural parser-error prevalence.
- The synthetic experiment does not measure missing listings, total source
  coverage, complete parser collapse, multi-error listings, real provider
  formats, or user outcomes.
- Real-product monitoring would eventually require manual review of a random
  sample, including listings the model did not flag. That is a considered
  future layer, not something to build for this prototype without a new scope
  decision.
- The API key belongs only in `.env.eval.local` and must never appear in
  committed artifacts or logs.

## Evidence And Publication State

- Full protocol and experiment history:
  `eval/AI_QA_EVAL_PLAN.md`.
- Final run artifacts:
  `eval/runs/extraction-v1-final-600/`.
- Human-readable final report:
  `eval/runs/extraction-v1-final-600/report.md`.
- Public case study:
  `https://mich-mayer.github.io/flatfeed/case-study.html`.
- The public HTML and Markdown case-study sources report only the new final
  600-listing result. They explain the experiment setup, all seven field
  results, the one invalid output, the stopping decision, and a bounded
  15,000-check AI API cost scenario.
- Earlier model-iteration scores are not shown on those public case-study
  surfaces.
- The cost scenario uses the official 12,398 re-lettings reported for Berlin's
  six state-owned housing companies excluding Berlinovo as an order-of-magnitude
  proxy, not as a count of online ads. The rounded 15,000-check workload,
  measured `$35/year` pattern, and buffered `$45/year` scenario are not
  measured production cost.
- The new final result is published at the public GitHub Pages URL and was
  verified there on 2026-07-31.
- The local case-study sources now describe the saved-filter Telegram flow as
  an implemented capability and retain the synthetic/no-live-source boundary.
- The local case-study sources use the product-first Problem / Solution / Built /
  Role / AI / Results / Learned structure and demonstrate the product only
  through captured screens. This local restructure is not deployed yet.
- The 2026-08-05 demo-only migration passed 348 unit tests, the 15-case
  deterministic parser evaluation, the public eval-number sync check, and
  desktop/mobile browser QA of the case-study page with no console errors.
- The case-study source reserves three Telegram captures for the saved filter,
  canonical listing card without a separate match-reason message. Existing
  demo-era reason captures remain out of the public page. GitHub Pages
  deployment must be verified from the workflow and public URL after each push.

## Portfolio Completion Decision

The current scope is a working saved-filter prototype on synthetic data, not a
live housing service. Keep deterministic matching evidence and bounded AI QA
evaluation stable. Background notifications are implemented and run only when
`BOT_BACKGROUND_ENABLED=true`; the current public demo keeps that switch off.
Live source integration and production validation remain outside the intended
scope rather than roadmap commitments.

## Maintenance Rule

Do **not** update this file after every prompt. Update it in the same change
only when at least one of these materially changes:

- product scope or an implemented product boundary;
- accepted/rejected model configuration;
- completed evaluation result or consumed dataset;
- public evidence or deployment state;
- the recommended next step;
- a constraint that a future agent must not violate.

Keep it short and replace stale status rather than appending a chat diary.
Detailed reasoning remains in the canonical artifact linked from the relevant
section. Before handoff, verify every changed fact against repository artifacts
and update the **Last verified** date.
