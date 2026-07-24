# FlatFeed Current Status

**Last verified:** 2026-07-24  
**Purpose:** short handoff for a new human or AI work session. Read this after
`AGENTS.md` / `CLAUDE.md` and before proposing the next experiment.

This file records changing project state. Stable product rules belong in
`docs/PROJECT_CONTEXT.md`; working rules belong in `docs/agent-workflow.md`;
the full experiment history and contracts belong in
`eval/AI_QA_EVAL_PLAN.md`.

## Product State

- FlatFeed is a product-first portfolio prototype that gives renters one
  Telegram feed for Berlin WBS listings matching four saved criteria: WBS,
  district, maximum Kaltmiete, and rooms.
- The implemented demo uses one synthetic source adapter. It does not scrape or
  redistribute real housing-company listings and does not claim live source
  coverage or renter outcomes.
- Parsing and matching are deterministic and fail closed on unknown critical
  values.
- AI QA is a bounded, admin-only parser check. It may flag a suspected parser
  error for human review, but it cannot mutate parsed listings, matching, or
  user-facing cards.
- The public Telegram demo still uses the deterministic mock provider. No
  hosted model from the offline experiment is integrated into product runtime.

## What The Offline AI QA Experiment Tested

The experiment used synthetic listing text with hidden ground truth to test
whether a hosted model could compare the raw listing with deterministic parser
output and identify:

1. whether the parser made an error;
2. which field was wrong;
3. whether a clean parse could pass without a false alert;
4. whether every attempted check returned a valid structured response.

The seven evaluated fields were WBS, district, Kaltmiete, rooms,
address/postal code, floor, and Warmmiete. The matching-critical fields were
WBS, district, Kaltmiete, and rooms.

The four simple product-facing metrics are:

- **Parser Error Detection Rate:** detected corrupted listings divided by all
  corrupted listings.
- **False Alert Rate:** clean listings incorrectly flagged divided by all clean
  listings.
- **Correct Field Detection Rate:** corrupted listings where the model named
  the correct field divided by all corrupted listings.
- **Successful Check Rate:** schema-conforming responses divided by all
  attempted checks.

Per-field results remain necessary guardrails because a strong aggregate can
hide a weakness in one matching-critical field.

## Final Selected Configuration And Result

The final selected configuration was:

- model: `gpt-5.6-terra`;
- reasoning effort: `high`;
- prompt: `terra-v1`;
- strict Structured Outputs;
- `max_output_tokens=256`;
- retries: `0`;
- service tier: `default`.

It passed a fresh 280-case frozen synthetic validation. It was then run exactly
once on the original independent 600-case locked holdout: 300 clean cases and
300 cases with exactly one planted parser error.

The four aggregate holdout metrics passed:

| Metric | Result | Gate |
|---|---:|---:|
| Parser Error Detection Rate | 291/300, 97.0% | at least 285/300 |
| False Alert Rate | 0/300, 0.0% | at most 9/300 |
| Correct Field Detection Rate | 291/300, 97.0% | at least 270/300 |
| Successful Check Rate | 600/600, 100.0% | at least 597/600 |

The matching-critical field guardrails were:

| Field | Result | Gate | Status |
|---|---:|---:|---|
| WBS | 75/75, 100.0% | at least 68/75 | Pass |
| district | 30/30, 100.0% | at least 27/30 | Pass |
| Kaltmiete | 60/60, 100.0% | at least 54/60 | Pass |
| rooms | 43/50, 86.0% | at least 45/50 | **Fail** |

The nine silent misses were seven neighboring-value rooms errors and two
postal-code substitutions. There were no false alerts and no technical
failures. The run cost `$1.011304`.

**Decision:** the overall result is a fail because the matching-critical rooms
guardrail failed. Terra high is not finally accepted. The stronger aggregate
metrics must not be used to override that decision.

## Experiment Boundaries

- The locked holdout is consumed. Do not rerun it, tune against it, regenerate
  it, or use its cases in another development set.
- Do not rerun the consumed calibration or frozen-validation datasets as a new
  acceptance attempt.
- Do not present balanced synthetic challenge-set metrics as production
  precision or natural parser-error prevalence.
- The synthetic experiment does not measure missing listings, total source
  coverage, complete parser collapse, multi-error listings, real provider
  formats, or renter outcomes.
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
  `eval/runs/terra-high-locked-holdout/`.
- Public case study:
  `https://mich-mayer.github.io/flatfeed/case-study.html`.
- The local HTML and Markdown case-study surfaces now report only the final
  600-listing result. They explain the experiment setup, metric formulas and
  purpose, all seven field results, the failed rooms guardrail, the stopping
  decision, and a clearly bounded 15,000-check inference-cost scenario.
- Earlier model-iteration scores are not shown on those public case-study
  surfaces.
- The cost scenario uses the official 12,398 re-lettings reported for Berlin's
  six state-owned housing companies excluding Berlinovo as an order-of-magnitude
  proxy, not as a count of online ads. The rounded 15,000-check workload and
  about `$65/year` conservative inference estimate are estimates, not measured
  production cost.
- These case-study changes are local until they are explicitly committed,
  pushed, and deployed.
- Commit `18c3c87afc5d53c05fcf9a714977111bfab54808` was pushed to `main`; its
  verification and GitHub Pages deployment passed.
- Last full local verification for that release: 292 unit tests passed,
  deterministic eval 15/15, public metric sync passed, and
  `git diff --check` passed.
- Current local verification for the pending case-study rewrite: 292 unit tests
  passed; deterministic eval passed 15/15; public final-result, field, decision,
  and cost sync passed; `git diff --check` passed; desktop and mobile browser
  checks found no page overflow or console errors.

## Recommended Next Step

Do not spend more API budget merely to produce a passing model result. The final
run provided enough evidence for this prototype: it showed that the approach
was promising and identified a specific weakness in rooms detection. Because
the evaluation used synthetic data, the next meaningful step is not further
tuning on the same benchmark, but recalibration and validation on permitted
real listings.

The product-level next step, if permission and terms allow it, is a small pilot
with one permitted live source plus manual review of a sample. This would test
the largest remaining uncertainty: transfer from synthetic listing formats to
real source data.

If the explicit goal is instead to continue model research, create a completely
fresh development-only comparison for `gpt-5.6-sol` without reusing any
consumed Terra/Luna or holdout cases. Predeclare the hypothesis, budget, gates,
and stopping rule before any API call. A fresh calibration and validation
would be justified only if that screen advances.

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
