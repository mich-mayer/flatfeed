# Extraction-v1 Final Synthetic Evaluation

**Decision:** passed every predeclared synthetic acceptance gate. The result
supports the feasibility of the admin-only parser check, but does not authorize
product-runtime integration.

## Setup

- Model: `gpt-5.6-terra`
- Reasoning effort: `high`
- Prompt: `extraction-v1`
- Output: strict Structured Outputs, maximum 768 tokens
- Dataset: 600 new synthetic listings generated with seed `20261001`
- Composition: 300 clean listings and 300 listings with one planted parser
  error
- Execution: one final run, zero retries, no post-run tuning or rescoring
- Isolation: no model-input, raw-text, or case-ID overlap with 22 prior input
  artifacts

The model received only raw listing text and returned exact source quotes for
eight values. Deterministic code compared those values with the parser
snapshot. A mismatch or unreadable value produced one admin-facing outcome:
`review_required`.

## Overall Results

| Metric | Result | Predeclared gate | Outcome |
|---|---:|---:|---|
| Parser Error Detection Rate | 300/300 (100.0%) | at least 294/300 | Pass |
| Correct Field Detection Rate | 300/300 (100.0%) | at least 294/300 | Pass |
| False Alert Rate | 0/300 (0.0%) | at most 3/300 | Pass |
| Successful Check Rate | 599/600 (99.8%) | at least 597/600 | Pass |

The balanced challenge set produced 300 correct alerts and no false alerts.
That gives a challenge-set precision of 300/300, but it is not an estimate of
production precision because real parser-error prevalence was not measured.

## Results By Field

| Field | Correct detections | Predeclared gate | Outcome |
|---|---:|---:|---|
| WBS | 75/75 (100.0%) | at least 74/75 | Pass |
| Kaltmiete | 60/60 (100.0%) | at least 59/60 | Pass |
| Rooms | 50/50 (100.0%) | at least 49/50 | Pass |
| Address / postal code | 40/40 (100.0%) | at least 39/40 | Pass |
| District | 30/30 (100.0%) | 30/30 | Pass |
| Floor | 25/25 (100.0%) | 25/25 | Pass |
| Warmmiete | 20/20 (100.0%) | 20/20 | Pass |

## One Invalid Check

One clean listing returned a Kaltmiete evidence quote that was not present
verbatim in the raw listing text. Local validation rejected that output, so the
case has no usable AI decision. It was not retried, did not create a false
alert, and remains counted as the single unsuccessful check.

## Operations

- Recorded API cost: `$1.412906`
- Cost per attempted listing: `$0.0023548433`
- Input tokens: 302,377
- Output tokens: 67,346
- Reasoning tokens: 6,802
- Cached input tokens: 0
- Median latency: 1,708.89 ms
- 95th-percentile latency: 4,276.15 ms

The run stayed below the frozen `$7.61` hard limit.

## Evidence Boundary

This is balanced synthetic challenge-set evidence. It does not measure
production accuracy, natural parser-error prevalence, real-source formats,
missing listings, source completeness, or renter outcomes. The next meaningful
test is a manually labelled sample of permitted real listings. No further
synthetic tuning or product integration is authorized by this result.

Machine-readable evidence:

- `report.json`
- `run_manifest.json`
- `predictions.jsonl`
- `../extraction-v1-final-600-configuration-freeze.json`
