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
  not measured;
- the hosted-model experiment produced the frozen synthetic validation results
  below.

**Synthetic frozen validation**

| Metric | Result | What it means |
|---|---:|---|
| Parser Error Detection Rate | 99.3% (139/140) | The checker alerted on 139 of 140 listings containing a planted parser error. |
| False Alert Rate | 0.7% (1/140) | The checker incorrectly alerted on 1 of 140 clean listings. |
| Correct Field Detection Rate | 99.3% (139/140) | The checker both found the error and named the affected field in 139 of 140 corrupted listings. |
| Successful Check Rate | 100.0% (280/280) | Every attempted check returned a valid response that the evaluation could score. |

All four matching-critical field guardrails passed: WBS 56/56, district 10/10,
Kaltmiete 21/21, and rooms 20/21. Address/postal code, floor, and Warmmiete
were also checked as diagnostic fields. The one missed parser error concerned
rooms; the one false alert concerned WBS.

A later one-time 600-case synthetic locked holdout passed all four aggregate
scorecard metrics but did not confirm the configuration: the predeclared
matching-critical rooms guardrail failed. I therefore kept the result as a
measured limitation rather than treating the checker as finally accepted.

Not demonstrated yet:

- whether real WBS renters adopt and trust the feed;
- whether one permitted live source can stay complete and fresh;
- whether the feed saves time or improves application outcomes;
- whether the synthetic AI QA result transfers to real listing formats and
  error rates.

The scorecard is a balanced synthetic challenge set, not a claim of production
accuracy. With permission to use real listings, I would require an admin to
review every AI alert and also audit a random sample of listings with no alert;
otherwise missed parser errors would remain invisible. Missing listings need a
separate source-coverage check and are outside this prototype.

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
