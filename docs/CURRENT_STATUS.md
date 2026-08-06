# FlatFeed Current Status

**Last verified:** 2026-08-05
**Purpose:** short handoff for a new human or AI work session. Read this after
`AGENTS.md` / `CLAUDE.md` and before proposing the next experiment.

This file records changing project state. Stable product rules belong in
`docs/PROJECT_CONTEXT.md`; working rules belong in `docs/agent-workflow.md`;
the full experiment history and contracts belong in
`eval/AI_QA_EVAL_PLAN.md`.

## Product State

- FlatFeed is a product-first portfolio prototype that demonstrates one guided
  Telegram scenario for reducing repeated checks across Berlin WBS listings with four criteria:
  WBS type, district, maximum Kaltmiete, and rooms.
- The implemented demo uses one synthetic source adapter. It does not scrape or
  redistribute real housing-company listings and does not claim live source
  coverage or user outcomes.
- Parsing and matching are deterministic and fail closed on unknown critical
  values.
- The public product surface is the Telegram prototype; the case study presents
  its captured product walkthrough and evidence. Saved-filter setup,
  arbitrary `Show matches` requests, persistent reply-keyboard actions,
  background user notifications, the Streamlit dashboard, public admin panel,
  unfiltered catalog browser, and mock QA tour are outside the current scope.
- `/start` reaches a real matching result in two guided steps: one authored
  four-field example, then a short match explanation followed by one canonical
  card produced by the deterministic matching, local activity-check, and card
  formatter path. The demo stores no personal filter.
- Result actions are limited to replaying the scenario, opening the optional
  matching explanation, or reading the case study. Old filter/match commands
  and callbacks redirect to the demo without writing state. `/delete` remains
  unadvertised only so returning users can remove legacy records.
- The public Telegram demo makes no model call. Optional runtime AI QA remains
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
- The case-study sources now describe the implemented Telegram evidence as one
  guided matching scenario, while keeping a saved-filter feed as the unbuilt
  product concept rather than a current capability.
- The 2026-08-05 demo-only migration passed 348 unit tests, the 15-case
  deterministic parser evaluation, the public eval-number sync check, and
  desktop/mobile browser QA of the case-study page with no console errors.
- The case-study walkthrough is intended to use captured Telegram evidence so
  it remains available without running the bot. The GitHub Pages URL still
  serves the prior public version until this work is committed and deployed.

## Portfolio Completion Decision

No further product or user testing is planned for this portfolio prototype.
Keep the functional Telegram walkthrough, deterministic matching evidence and
bounded AI QA evaluation stable. Live source integration and production
validation remain outside the intended scope rather than roadmap commitments.

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
