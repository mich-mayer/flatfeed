# FlatFeed Case Study

FlatFeed is a working Telegram prototype for matching Berlin WBS apartment
listings against one saved filter: WBS type, district, maximum Kaltmiete, and
room count. The current version runs on a synthetic catalog. It demonstrates
the product workflow and its reliability controls; it does not demonstrate live
source coverage or renter outcomes.

WBS (Wohnberechtigungsschein) is a certificate used to qualify for subsidized
housing in Berlin. Kaltmiete is the base rent, excluding operating and heating
costs.

## 1. Product Hypothesis

The premise: WBS renters re-read fragmented listings and repeat the same basic
checks on each one. FlatFeed tests one narrow job: save one filter, then see
matching listings in one consistent Telegram format.

This premise has not yet been validated through renter research. The prototype
exists to make that next test concrete, not to imply a launched housing service.

## 2. Product and Role

The main path is:

```text
Filter → Collect → Prepare → Match → Deliver
```

- A user saves WBS type, district, maximum Kaltmiete, and rooms.
- A source adapter adds newly found listings to one catalog.
- Fixed rules normalize listing fields and estimate walks to the nearest S- and
  U-Bahn stations.
- Deterministic rules compare each new listing with the saved filter.
- Matching listings are sent to Telegram so renters can open the source and
  apply.

I defined the WBS renter problem and product scope; chose which fields determine
a match and how missing data is handled; set the AI boundary; and designed the
evaluation plan and acceptance criteria. I implemented the Telegram prototype
with Claude Code and Codex as coding collaborators.

## 3. Key Decisions

### A first-pass filter, not a final eligibility decision

I chose WBS type, district, maximum Kaltmiete, and rooms to reduce the listings
a renter must review. FlatFeed uses them to create an initial shortlist; renters
still verify complete eligibility and application details on the source page.

### Rules decide which listings appear

Parsing and matching follow fixed rules, so the reason for each match can be
traced to the saved filter. The repository also contains an optional admin QA
workflow that can flag a suspected parsing error. The public demo uses a
deterministic mock provider. QA findings cannot automatically change the
listing or the match.

### One product flow across sources

Each permitted source would be normalized into the same listing format before
matching, so users keep one filter and one feed. The current prototype exercises
this design with one synthetic source. Completeness and freshness across real
sources are still untested, and there is no live housing-company ingestion in
this version.

## 4. Evidence and Limits

Demonstrated now:

- a user can save a filter and receive matches from a synthetic catalog in
  Telegram;
- Telegram listing summaries include estimated walks to the nearest S- and
  U-Bahn stations, calculated from synthetic coordinates in the demo;
- on 600 new synthetic listings, a hosted model plus deterministic comparison
  found and localized all 300 planted parser errors, raised no false alerts on
  300 clean listings, and returned 599 valid checks.

### Final AI QA evaluation

**AI QA evaluation · synthetic data · 600 listings**

FlatFeed uses deterministic rules to parse listings and match them to renter
filters. I tested a hosted model as an admin-only second check, not as part of
renter matching. A finding does not alter the current listing; an admin can use
it to decide whether parsing rules should change for future listings. This was a
separate evaluation, and the model was not integrated into the product. The
final test used 600 synthetic listings: 300 clean listings and 300 listings
containing exactly one planted parser error.

**Decision: passed the synthetic benchmark; not integrated into the product.**
The checker found and localized all 300 planted errors and raised no false
alerts on 300 clean listings. One clean listing produced an invalid evidence
quote, so 599 of 600 checks returned a usable result. Every predeclared gate
passed.

Overall results show how often the checker found an error, whether it named the
right field, and how often it wrongly flagged a clean listing. Results by field
make sure a strong average does not hide a weak matching-critical field.

| Overall metric | Final result | How it is calculated | Product focus | Prototype target |
|---|---:|---|---|---|
| Parser Error Detection Rate | 100.0% (300/300) | Corrupted listings that produced an alert ÷ 300 corrupted listings | How many parser mistakes reach admin review | At least 98% (294/300), met |
| False Alert Rate | 0.0% (0/300) | Clean listings that produced an alert ÷ 300 clean listings | Unnecessary admin reviews caused by the checker | At most 1% (3/300), met |
| Correct Field Detection Rate | 100.0% (300/300) | Corrupted listings where the wrong field was correctly named ÷ 300 corrupted listings | Whether an alert tells an admin where to investigate | At least 98% (294/300), met |
| Successful Check Rate | 99.8% (599/600) | Valid structured model responses ÷ 600 attempted checks | Whether the check completes in a form the system can use | At least 99.5% (597/600), met |

These thresholds were predeclared product acceptance criteria for this
prototype, not universal industry benchmarks.

Each corrupted test listing contained one planted error. The table groups
results by the field that was wrong. WBS, district, Kaltmiete, and rooms affect
matching; the other fields help an admin diagnose the listing.

| Field | Role | Correct detections | Predeclared target | Outcome |
|---|---|---:|---:|---|
| WBS | Matching-critical filter | 75/75 (100.0%) | At least 74/75 | Target met |
| District | Matching-critical filter | 30/30 (100.0%) | 30/30 | Target met |
| Kaltmiete | Matching-critical filter | 60/60 (100.0%) | At least 59/60 | Target met |
| Rooms | Matching-critical filter | 50/50 (100.0%) | At least 49/50 | Target met |
| Address / postal code | Diagnostic listing field | 40/40 (100.0%) | At least 39/40 | Target met |
| Floor | Diagnostic listing field | 25/25 (100.0%) | 25/25 | Target met |
| Warmmiete | Diagnostic listing field | 20/20 (100.0%) | 20/20 | Target met |

No planted parser error was missed. One clean listing failed the evidence-quote
validation, so the checker returned no usable decision for that listing. It did
not create a false alert and was not retried.

The final configuration used `gpt-5.6-terra` with high reasoning effort and
strict Structured Outputs. The model saw only raw listing text and returned
exact source quotes for eight values. Deterministic code compared those values
with the parser snapshot and created the single admin decision
`review_required`. The model did not change parsing, matching, or renter-facing
listing summaries.

Within the prototype's planned budget for real-model testing, I used the final
benchmark once and kept its result unchanged.

> The final run met every synthetic acceptance gate, so I stopped synthetic
> tuning. With no permitted live dataset available, the next useful test is the
> current synthetic Telegram flow with WBS renters.

### Model-cost scenario at Berlin municipal-listing scale

Berlin's six state-owned housing companies covered by the 2024 cooperation
report, excluding Berlinovo, reported 12,398 apartment re-lettings. This is the
closest official volume proxy I found, not a count of online ads. Because no
consolidated public count of unique listings is available, I rounded up to a
planning scenario of 15,000 unique listing checks per year.

- **Measured run pattern:** about **$35 per year** or **$2.94 per month**:
  15,000 × $0.00235 per check. The final 600-check run cost `$1.412906`.
- **Planning case with a 25% buffer:** about **$45 per year** or **$3.68 per
  month**: 15,000 × $0.00294 per check.

This is an estimate of AI API calls only, based on one check per unique
listing per prompt version and the prices recorded on 30 July 2026. It excludes
source access, hosting, monitoring, duplicate listings, price changes,
differences in real-listing length, and human review. The 12,398 re-lettings
establish an order of magnitude, not the exact number of ads that a live system
would process.

Evidence:

- [Evaluation contract](eval/AI_QA_EVAL_PLAN.md)
- [Final 600-listing report](eval/runs/extraction-v1-final-600/report.md)
- [Official Berlin 2024 housing-company report announcement](https://www.berlin.de/sen/stadt/presse/pressemeldungen/pressemitteilung.1628093.php)

Not demonstrated yet:

- whether real WBS renters adopt and trust the feed;
- whether permitted Berlin WBS sources can be combined into one complete,
  fresh feed;
- whether the feed reduces monitoring time and helps renters apply sooner;
- how often real source formats cause FlatFeed to miss a suitable listing;
- whether a real model tested on planted synthetic errors can detect naturally
  occurring parser errors in permitted live listings.

The evaluation used balanced synthetic cases, not live listings or natural
production error rates. The prototype has no permitted live dataset, so
accuracy on real listing formats and naturally occurring parser errors remains
unmeasured. Missing listings need a separate source-coverage check and are
outside this prototype.

## 5. Next Test

The synthetic evaluation answered the technical feasibility question for this
prototype. With no permitted live source available, the next useful test is a
moderated walkthrough of the current synthetic Telegram flow with a small group
of WBS renters—not another generated benchmark.

- **Learn:** Do renters understand the one-filter feed and see how it could
  reduce repeated monitoring?
- **Measure:** Filter setup completion; whether participants can explain why a
  listing appeared; time to find and open a relevant listing in the demo; and
  the points where the flow feels unclear or untrustworthy.
- **Decide:** Keep or revise the renter flow based on repeated usability
  problems. Treat access to real sources as a separate feasibility risk, not as
  a capability of this prototype.
