# AI QA Failure Analysis

**Status:** completed analysis of the consumed 600-case synthetic holdout
**Scope:** development input for a new checker; not new acceptance evidence
**Source run:** `eval/runs/terra-high-locked-holdout/`

## Why this analysis exists

The final `terra-v1` check found 291 of 300 planted parser errors but silently
missed nine. Before changing the checker, this document separates what the run
actually shows from guesses about why the model failed.

The old holdout is consumed. Its cases may be inspected for failure analysis,
but they must not be sent to a model again, copied into a development dataset,
or used as a new acceptance attempt.

## The nine missed errors

Every missed case contained one direct contradiction between the raw listing
text and the parser snapshot. The model returned
`{"has_error": false, "error_field": null}` for all nine.

| Case | Field | Explicit value in listing | Value in parser snapshot |
|---|---|---:|---:|
| `aqa-1e988b94ea5e2729caed` | rooms | 5 | 4 |
| `aqa-370a952e6ce9ea32530d` | rooms | 2 | 3 |
| `aqa-5273bef32135c8fc8284` | rooms | 3 | 3.5 |
| `aqa-66ff6ce1b3743643a207` | postal code | 12459 | 12043 |
| `aqa-751e1e788681fc9414fc` | rooms | 2 | 1 |
| `aqa-8101d09d5113a52cd5f2` | rooms | 3 | 2 |
| `aqa-832b4dbe6c090bad9878` | postal code | 13585 | 12459 |
| `aqa-ae82097472f78cce311a` | rooms | 1 | 2 |
| `aqa-e55d0c68c99050eb7f25` | rooms | 3 | 2 |

## What the evidence shows

1. **Seven misses were neighboring room values.** The source text used direct
   labels such as `5 Zimmer` or `Zimmeranzahl: 1,5`. The parser snapshot
   differed by 0.5 or 1 room.
2. **Two misses were postal-code substitutions.** In both cases the street and
   district remained plausible while the explicit five-digit postal code
   differed.
3. **These were silent misses, not field-label mistakes.** Whenever the model
   did raise an alert in the holdout, it named the correct field. In these nine
   cases it raised no alert at all.
4. **No single value pair or listing layout explains the rooms misses.** The
   same kinds of neighboring-value changes were detected in other holdout
   cases. The failure is therefore not isolated to one number or one template.
5. **The existing prompt already names both risks.** `terra-v1` requires exact
   room comparison, an independent postal-code comparison, and a mandatory
   seven-field inspection. The misses cannot be explained by those instructions
   being absent.

## What the evidence does not show

The model returned only a binary result and an optional field name. It did not
return the source value it read or the evidence it used. We therefore cannot
honestly say whether it misread the source, skipped a field, or compared the
values incorrectly.

Reasoning-token counts do not provide a reliable explanation. The missed cases
used between 0 and 43 reasoning tokens, and the stored output contains no
auditable comparison trace.

## Why another longer hidden checklist is not the next fix

A prior fresh development screen already tested `terra-v2`, which added an
internal seven-field equality ledger and final rooms/WBS re-check. On the same
64 cases it improved rooms from 19/20 to 20/20, but reduced WBS from 19/20 to
17/20 and other fields from 8/8 to 6/8. Total correctness fell from 62/64 to
59/64, so that prompt was stopped.

This means that adding more instructions without changing the observable model
output is not a sufficiently supported improvement strategy.

## Hypothesis for the next implementation step

Keep the checker small, but make its comparison inspectable. A new development
candidate should return:

- `review_required`: the single routing decision; every `true` result is shown
  to the admin;
- `review_reason`: `direct_mismatch` for a clear contradiction or
  `unclear_source` when the source cannot be compared reliably;
- `error_field`: one of the seven evaluated fields, or `null`;
- `source_value`: the value read from the listing for the suspected field;
- `snapshot_value`: the value being challenged;
- `evidence_quote`: a short exact quote from the raw listing.

The reason explains why the listing needs review; it does not create a second
queue or suppress an alert. The surrounding code should reject a review when
its evidence quote is not present in the raw text, its field is unsupported, or
its snapshot value does not match the challenged parser field.

In the synthetic benchmark, every `review_required=true` response counts as an
alert. An alert on a clean listing is therefore a false alert regardless of its
reason, and correct-field credit still requires the expected `error_field`.
This prevents a model from passing by marking every listing as unclear.

This is an offline evaluation candidate only. It must not modify listing data,
matching, cards, the Telegram runtime, or the historical `terra-v1` artifacts.
No hidden ground truth or case metadata may enter the model request.

## Development comparison

The parallel local contract is implemented in
`eval/ai_qa_review_contract.py`. It does not edit the frozen `terra-v1` prompt
or scorer in place. The development dataset is frozen in
`eval/datasets/review_v1_development/`:

- 120 cases generated with seed `20260901`;
- 50 clean cases and 70 cases with exactly one planted error;
- 20 rooms errors;
- 10 address/postal-code errors, including six postal-code substitutions;
- separate model-input and hidden-truth files;
- zero overlap with 21 prior model-input artifacts by complete model input,
  raw listing text, and case ID.

The current standard `gpt-5.6-terra` prices were re-checked against the official
OpenAI pricing page on 2026-07-30. The exact paired configuration was then
frozen in
`eval/runs/review-v1-development-configuration-freeze.json`. The baseline and
candidate were each run once on the same cases with high reasoning, no retries,
and strict Structured Outputs.

| Result | `terra-v1` baseline | `review-v1` candidate |
|---|---:|---:|
| Successful checks | 120/120 | 120/120 |
| Parser errors detected | 66/70 | 66/70 |
| Correct fields | 66/70 | 66/70 |
| False alerts | 0/50 | 0/50 |
| Rooms | 16/20 | 17/20 |
| District | 8/8 | 7/8 |
| Other five field groups | 42/42 | 42/42 |
| Recorded API cost | `$0.194043` | `$0.272532` |

The candidate recovered one decimal rooms mismatch that the baseline missed:
`Zimmer: 2,5` versus snapshot `2.0`. It still silently missed three direct
`2 Zimmer` contradictions and also missed one explicit district contradiction:
`Bezirk Pankow` versus snapshot `Mitte`. It produced no `unclear_source`
reviews. Every alert it did produce contained valid evidence.

The richer output therefore improved inspectability for alerts and recovered
one rooms case, but it did not improve total detection. The gain was exchanged
for a new district miss. The candidate failed its predeclared development
gates: at least 68/70 detected errors, at least 67/70 correct fields, 19/20
rooms, and 8/8 district were all required.

The paired run cost `$0.466575` in total, below the conservative `$4.92` hard
limit. There were no technical failures. Full artifacts and the gate decision
are stored in `eval/runs/review-v1-development-comparison/comparison.json`.

## Decision

`review-v1` is rejected as the configuration for a new 600-case evaluation.
The final 600-case dataset must not be generated or sent to the model yet. The
120-case development run is consumed as a one-shot paired screen, although its
cases may be inspected and reused explicitly as development data.

Adding evidence fields is useful for admin review, but asking the model to both
extract values and decide whether they match still permits silent comparison
misses. The next bounded hypothesis is to make the model return the source
values for every evaluated field and let deterministic code compare them with
the parser snapshot. This keeps AI limited to reading the listing and moves the
exact equality decision into testable code. It should be implemented and
tested locally before deciding whether another development API run is justified.

## Extraction-v1 development result

The next hypothesis was implemented and tested on the reused development set.
The
`extraction-v1` model contract receives only raw listing text and returns a
short exact quote or `null` for each of eight source fields: WBS, Kaltmiete,
rooms, address, postal code, district, floor, and Warmmiete. Address and postal
code remain one evaluation group, so the scorecard still has seven fields. The
model does not return separate `found`, `not_mentioned`, or `unclear` statuses.

The model never receives the parser snapshot. Deterministic code normalizes the
eight extracted values, compares them with the snapshot, and sends any direct
mismatch or unreadable value to one admin review route. These are diagnostic
reasons inside the report, not separate product statuses. The local contract
rejects invented quotes and incomplete output.

Tests cover each comparison group and all 120 existing development cases. The
120-case test supplies known-correct evidence to the comparator, so it proves
that the deterministic comparison detects the planted differences. It does
not prove that the model can extract the evidence reliably.

A reproducible no-network plan is stored in
`eval/runs/extraction-v1-development-dry-run.json`. It schedules one
`gpt-5.6-terra` high-reasoning request for each of the 120 reused development
cases, zero retries, and one model-availability check. The deliberately
conservative hard budget is `$1.91`; pricing was refreshed against the
official OpenAI pricing page on 2026-07-30 before the configuration freeze.

The frozen run completed all 120 requests with no retry or technical failure
and cost `$0.369260`. Its first local score exposed a comparator bug: the model
returned valid exact quotes with whitespace-separated labels, bare postal
codes, and `Stockwerk` floor labels, but the normalizer expected narrower
formats. The unchanged original report therefore showed 38/50 false alerts and
only 33/70 correct fields.

The comparator was generalized and covered by regression tests. The same saved
model outputs were rescored with zero additional API calls and zero additional
cost:

| Metric | Rescored result |
|---|---:|
| Successful checks | 120/120 |
| Parser errors detected | 70/70 |
| Correct fields | 70/70 |
| False alerts | 0/50 |
| Rooms | 20/20 |
| District | 8/8 |

All development gates passed. This authorizes preparation of one fresh
600-case synthetic evaluation for `extraction-v1`, not reuse of the consumed
holdout. The post-run comparator fix is explicitly development tuning, so the
120-case result is not final evidence and is not published in the case study.
Both the original report and the transparent rescore are retained under
`eval/runs/extraction-v1-development/`.

## Final successor result

The development result above authorized one fresh 600-case final evaluation.
That evaluation is now complete. `extraction-v1` found and localized all
300/300 planted errors, raised 0/300 false alerts, and returned 599/600 usable
checks. Every predeclared aggregate and per-field gate passed.

One clean case returned an evidence quote that was not present verbatim in the
source text. It was rejected locally, not retried, and did not create a false
alert. The final run cost `$1.412906`.

The accepted conclusion is limited to synthetic feasibility. Product-runtime
integration remains unauthorized; the next meaningful check is transfer to a
manually labelled sample of permitted real listing formats. Canonical final
artifacts are under `eval/runs/extraction-v1-final-600/`.
