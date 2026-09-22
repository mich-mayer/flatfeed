# Prototype status and limitations

**Reviewed:** 22 September 2026.

FlatFeed is a completed portfolio prototype over synthetic Berlin WBS listings.
It demonstrates a saved-filter Telegram workflow and a separate offline AI
evaluation. It is not a live housing service; no renter outcomes have been
measured.

## Implemented product

- One saved filter: WBS type, district, maximum Kaltmiete and rooms.
- Deterministic parsing, matching and consistent listing cards. Missing values
  required by a filter do not produce a match.
- Up to three matches on demand, filter editing, reset and confirmed data
  deletion.
- Background collection and deduplicated notifications, enabled only when
  `BOT_BACKGROUND_ENABLED=true`; the default prototype keeps this off.
- One synthetic source adapter with ingestion history, activity checks and
  source-health monitoring.
- A [public case study](https://mich-mayer.github.io/flatfeed/case-study.html)
  with seven captured screens from the implemented Telegram flow.

The [product architecture](PRODUCT.md) describes behavior and data storage.
The user-facing product path makes no model call. A separate optional runtime
QA path can send admin-only alerts when explicitly enabled; it cannot modify
listing data, matching or cards.

## Accepted evaluation evidence

The separate offline `extraction-v1` check used `gpt-5.6-terra` with high
reasoning and strict Structured Outputs. The model returned source quotes from
raw listing text; deterministic code compared the extracted values with parser
snapshots. The model did not receive the snapshots or scoring truth.

One frozen synthetic run contained 600 cases: 300 clean and 300 with one
planted parser error. There were no retries or post-run tuning.

| Metric | Recorded result |
|---|---:|
| Planted errors detected | 300/300 |
| Correct field identified | 300/300 |
| False alerts on clean cases | 0/300 |
| Usable checks | 599/600 |

All predeclared gates passed. One clean case returned a quote absent from its
source text; local validation rejected it without a retry or false alert.
The recorded API cost for this run was `$1.412906`.

This is accepted synthetic feasibility evidence. The evaluated configuration
is not integrated into the Telegram runtime, and its results do not validate
the different optional runtime QA contract.

- [Final report](../eval/runs/extraction-v1-final-600/report.md)
- [Final protocol and acceptance gates](../eval/AI_QA_EVAL_PLAN.md)
- [Evidence index and unsuccessful earlier experiments](../eval/README.md)

## Limits of the evidence

Live source access, provider formats, housing coverage, natural parser-error
prevalence, multi-error listings, missing listings and renter outcomes remain
unvalidated. Transit times are geometric estimates, not routed walking times.

Both the earlier locked holdout and final extraction dataset are consumed.
Their recorded results remain frozen; repeating or tuning against them would
not provide independent acceptance evidence. Further real-source validation
would require permitted data and independent labels, including a random
sample of unflagged listings. It is outside the completed prototype scope.
