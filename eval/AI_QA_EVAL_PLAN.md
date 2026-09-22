# Final offline AI QA evaluation

**Accepted result:** `extraction-v1`, one frozen 600-case synthetic evaluation
completed on 30 July 2026. This page describes the accepted contract; the
[original protocol and experiment history](archive/AI_QA_EVAL_HISTORY.md) is
preserved unchanged as historical evidence.

[Final report](runs/extraction-v1-final-600/report.md)
· [Evidence and code guide](README.md)
· [Configuration freeze](runs/extraction-v1-final-600-configuration-freeze.json)

## Question and boundary

Can independent source-quote extraction, followed by deterministic comparison,
identify planted errors in synthetic parser snapshots?

The model receives **only raw listing text**. It does not receive the parser
snapshot, truth, split labels or corruption metadata. It returns an exact quote
or null for each of eight fields. Code validates the quotes, normalizes the
values and compares them with the snapshot, producing `review_required` and
field-level issues. Address and postal code form one comparison group, so eight
extracted fields map to seven evaluated groups.

This is an offline feasibility test. It did not send findings to a runtime
admin queue, change Telegram behavior or integrate the evaluated configuration
into the product. The separate optional runtime QA path in
[`flatfeed/ai_qa.py`](../flatfeed/ai_qa.py) receives both text and a snapshot and
returns a model risk assessment. These results do not validate that path.

## Frozen setup

| Item | Recorded configuration |
|---|---|
| Model | `gpt-5.6-terra` |
| Reasoning | `high` |
| Prompt | `extraction-v1` |
| Output | Strict Structured Outputs; maximum 768 output tokens |
| Dataset | 600 new synthetic cases: 300 clean, 300 with one planted parser error |
| Isolation | No exact model-input, raw-text or case-ID overlap with 22 prior input artifacts |
| Execution | One final run; zero retries; no post-run tuning or rescoring |
| Result use | Synthetic feasibility evidence only; no runtime integration |

The final dataset was generated with seed `20261001` and frozen before the API
run. The predeclared corruption distribution was WBS 75, Kaltmiete 60, rooms 50,
address/postal code 40, district 30, floor 25 and Warmmiete 20.

## Acceptance gates and recorded results

| Metric | Gate | Result |
|---|---:|---:|
| Errors detected | at least 294/300 | 300/300 (100.0%) |
| Correct field identified | at least 294/300 | 300/300 (100.0%) |
| False alerts on clean cases | at most 3/300 | 0/300 (0.0%) |
| Usable checks | at least 597/600 | 599/600 (99.8%) |

Every field gate passed: WBS 75/75 (minimum 74), Kaltmiete 60/60 (59),
rooms 50/50 (49), address/postal code 40/40 (39), district 30/30 (30),
floor 25/25 (25), Warmmiete 20/20 (20).

One clean case returned a quote not present verbatim in the source text. Local
validation rejected it, with no retry and no false alert. It remains the one
unusable check; it must not be represented as a successful negative decision.

The recorded API cost was `$1.412906`. This is the cost of that run at its
recorded prices, not a production operating-cost measurement.

## Decision and limits

Accept the final synthetic feasibility result and stop synthetic tuning. Both
the earlier locked holdout and this final dataset are consumed. Do not rerun
them, tune against them, regenerate them in a research copy, or rescore them as
a new acceptance attempt.

This balanced, single-error challenge set does not measure production accuracy,
natural parser-error prevalence, multi-error listings, missing listings, source
completeness, actual provider formats or renter outcomes. Any future
real-source validation would require permitted data and independent manual
labels, including a random sample of unflagged listings. That is outside the
completed prototype scope.

Deterministic test-fixture reconstruction in a fresh disposable checkout, as
documented in [README](../README.md#development-checks), is separate from model
evaluation. It makes no API calls and does not create acceptance evidence.

## Inspect the evidence

- [Human-readable final report](runs/extraction-v1-final-600/report.md)
- [Machine-readable report](runs/extraction-v1-final-600/report.json)
- [Run manifest](runs/extraction-v1-final-600/run_manifest.json)
- [Predictions](runs/extraction-v1-final-600/predictions.jsonl)
- [Configuration freeze](runs/extraction-v1-final-600-configuration-freeze.json)
- [Dataset manifest](datasets/extraction_v1_final_600/dataset_manifest.json)
- [Model inputs](datasets/extraction_v1_final_600/model_inputs.jsonl)
- [Separate ground truth](datasets/extraction_v1_final_600/truth.jsonl)
- [Extraction contract](ai_qa_extraction_contract.py)
- [Deterministic comparator](ai_qa_extraction_compare.py)
- [Final execution and scoring](ai_qa_extraction_final.py)

Frozen datasets, predictions, reports, manifests and executable experiment
contracts retain their original bytes. Navigation is maintained here and in
[the evaluation guide](README.md), not by rewriting frozen artifacts.

## How the configuration evolved

The earlier model-judgment approach had silent misses on its consumed holdout.
The [failure analysis](AI_QA_FAILURE_ANALYSIS.md) records what was observed and
what could not be inferred. Subsequent `review-v1` and extraction-development
work used separate data before the final extraction configuration was frozen.
Unsuccessful iterations remain part of the evidence; they are not current
acceptance results.

The [historical protocol](archive/AI_QA_EVAL_HISTORY.md) preserves the original
contracts and chronological results. Its early definitions in which the model
receives a snapshot describe older configurations, not `extraction-v1`.
