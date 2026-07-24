# FlatFeed Case Study

FlatFeed is a working Telegram prototype for matching Berlin WBS apartment
listings against four renter criteria: WBS tier, district, maximum Kaltmiete,
and room count. The current version runs on a synthetic catalog. It demonstrates
the product workflow and its reliability controls; it does not demonstrate live
source coverage or renter outcomes.

WBS (Wohnberechtigungsschein) is a certificate used to qualify for subsidized
housing in Berlin. Kaltmiete is rent before utilities.

## 1. Product Hypothesis

The premise: WBS renters re-read fragmented listings and repeat the same basic
checks on each one. FlatFeed tests one narrow job: save one filter, then see
matching listings as consistent Telegram cards.

This premise has not yet been validated through renter research. The prototype
exists to make that next test concrete, not to imply a launched housing service.

## 2. Product and Role

The main path is:

```text
Filter → Normalize → Check → Match → Notify
```

- A renter sets four filter fields.
- Fixed parsing rules normalize listing text.
- The current synthetic adapter re-checks that a listing is still active in
  its local catalog.
- Deterministic rules compare all four fields and explain a match.
- An optional background path deduplicates newly seen matches against stored
  delivery history.

I defined the renter problem, product scope, matching and AI guardrails,
reliability trade-offs, and evaluation contract. I implemented the bot,
dashboard, and test harness with Claude Code and Codex as coding collaborators.

## 3. Key Decisions

### Four fields, not a generic search

The prototype keeps only the fields used in its match decision. Unknown rent or
room values fail closed instead of producing a confident-looking match. This is
a four-criteria match, not a complete assessment of every housing restriction.

### Rules decide what renters see

Parsing and matching are deterministic. The repository also contains an
optional admin QA workflow that can flag parser mismatches. The public demo uses
a deterministic mock provider. QA findings cannot automatically change
listings, matching rules, or renter-facing results.

### Reliability before source count

Before adding sources, I protected the core loop against stale and duplicate
results. Listings are re-checked as active before delivery, background
notifications skip matches already recorded as delivered, and /delete removes
the saved filter and delivery history from the FlatFeed database. Only one
synthetic source adapter is implemented; there is no live housing-company
ingestion in this version.

## 4. Evidence and Limits

Demonstrated now:

- a renter can save a four-field filter and receive matching Telegram cards;
- deterministic matching applies all four criteria and fails closed on unknown
  rent or rooms;
- the synthetic catalog checks activity before delivery, while background
  notifications deduplicate previously delivered matches;
- the deterministic synthetic regression suite passes; live-source accuracy is
  not measured.

### Final offline AI QA evaluation

**Offline AI QA evaluation · synthetic data · 600 listings**

FlatFeed uses deterministic rules to parse listings and match them to renter
filters. I tested a hosted model as an admin-only second check, not as part of
renter matching. The final evaluation used 600 synthetic listings: 300 clean
listings and 300 listings containing exactly one planted parser error.

**Decision: promising result; configuration not accepted.** The checker
detected 291 of 300 planted errors and raised no false alerts on 300 clean
listings. However, it correctly detected only 43 of 50 rooms errors, below the
predeclared minimum of 45. I therefore did not accept the configuration.

I used two levels of measurement. Overall metrics tested whether the checker
could find errors without creating unnecessary admin work. Field-level
guardrails tested whether a strong average was hiding a weakness in one of the
four fields that directly controls apartment matching.

| Overall metric | Final result | How it is calculated | Product focus | Prototype target |
|---|---:|---|---|---|
| Parser Error Detection Rate | 97.0% (291/300) | Corrupted listings that produced an alert ÷ 300 corrupted listings | How many parser mistakes reach admin review | At least 95% (285/300), met |
| False Alert Rate | 0.0% (0/300) | Clean listings that produced an alert ÷ 300 clean listings | Unnecessary admin reviews caused by the checker | At most 3% (9/300), met |
| Correct Field Detection Rate | 97.0% (291/300) | Corrupted listings where the wrong field was correctly named ÷ 300 corrupted listings | Whether an alert tells an admin where to investigate | At least 90% (270/300), met |
| Successful Check Rate | 100.0% (600/600) | Valid structured model responses ÷ 600 attempted checks | Whether the check completes in a form the system can use | At least 99.5% (597/600), met |

These thresholds were predeclared product acceptance criteria for this
prototype, not universal industry benchmarks.

Each corrupted listing contained one planted error. A field result counts how
often the checker both raised an alert and correctly named that field.
Matching-critical fields control the renter's filter; diagnostic fields help
inspect the listing but do not decide the four-field match.

| Field | Role | Correct detections | Predeclared target | Outcome |
|---|---|---:|---:|---|
| WBS | Matching-critical filter | 75/75 (100.0%) | At least 68/75 | Target met |
| District | Matching-critical filter | 30/30 (100.0%) | At least 27/30 | Target met |
| Kaltmiete | Matching-critical filter | 60/60 (100.0%) | At least 54/60 | Target met |
| Rooms | Matching-critical filter | 43/50 (86.0%) | At least 45/50 | **Target missed** |
| Address / postal code | Diagnostic listing field | 38/40 (95.0%) | Diagnostic only | 2 misses recorded |
| Floor | Diagnostic listing field | 25/25 (100.0%) | Diagnostic only | No misses |
| Warmmiete | Diagnostic listing field | 20/20 (100.0%) | Diagnostic only | No misses |

Nine planted errors were missed: seven neighboring-value rooms errors and two
postal-code substitutions. Rooms directly determine whether a listing matches a
renter's filter, so a miss could wrongly include or exclude an apartment. That
is why the configuration failed even though all four overall metrics met their
targets.

The final configuration used `gpt-5.6-terra` with high reasoning effort and
strict Structured Outputs. During development, I increased the model's
reasoning effort only when lower-effort configurations were insufficient. This
case study reports only the final independent 600-listing run.

Within the prototype's planned budget for real-model testing, I used the final
benchmark once and kept its result unchanged.

> The final run provided enough evidence for this prototype: it showed that the approach was promising and identified a specific weakness in rooms detection. Because the evaluation used synthetic data, the next meaningful step is not further tuning on the same benchmark, but recalibration and validation on permitted real listings.

### Model-cost scenario at Berlin municipal-listing scale

Berlin's six state-owned housing companies covered by the 2024 cooperation
report, excluding Berlinovo, reported 12,398 apartment re-lettings. This is the
closest official volume proxy I found, not a count of online ads. Because no
consolidated public count of unique listings is available, I rounded up to a
planning scenario of 15,000 unique listing checks per year.

- **Conservative planning case:** about **$65 per year** or **$5.38 per
  month**. This uses the final run's token volume without relying on a
  prompt-cache discount: 15,000 × $0.00430 per check.
- **Observed run pattern:** about **$25 per year** or **$2.11 per month**:
  15,000 × $0.00169 per check. The final 600-check run cost `$1.011304` with
  its observed caching pattern.

This is an estimate of model inference only, based on one check per unique
listing per prompt version and the prices recorded on 21 July 2026. It excludes
source access, hosting, monitoring, duplicate listings, price changes,
differences in real-listing length, and human review. The 12,398 re-lettings
establish an order of magnitude, not the exact number of ads that a live system
would process.

Evidence:

- [Evaluation contract](eval/AI_QA_EVAL_PLAN.md)
- [Final 600-listing report](eval/runs/terra-high-locked-holdout/reports/report.md)
- [Official Berlin 2024 housing-company report announcement](https://www.berlin.de/sen/stadt/presse/pressemeldungen/pressemitteilung.1628093.php)

Not demonstrated yet:

- whether real WBS renters adopt and trust the feed;
- whether one permitted live source can stay complete and fresh;
- whether the feed saves time or improves application outcomes;
- whether the synthetic AI QA result transfers to real listing formats and
  error rates.

The evaluation used balanced synthetic cases, not live listings or natural
production error rates. With permission to use real listings, I would require
an admin to review every AI alert and also audit a random sample of listings
with no alert; otherwise missed parser errors would remain invisible. Missing
listings need a separate source-coverage check and are outside this prototype.

## 5. Next Test

Next, I would test the complete flow with one permitted live source and a small
group of WBS renters. Alongside the renter test, a manually labelled sample
would check whether the synthetic AI QA result transfers to real listing
formats.

- **Learn:** Do renters understand why each listing appears and trust the
  standardized cards?
- **Measure:** Filter completion, listing opens, stale-open rate, plus
  human review of every AI alert and a random sample of listings with no alert.
- **Decide:** Add sources only if renters use the feed, source freshness is
  manageable, and the AI checker works on real listing formats without
  excessive misses or false alerts.
