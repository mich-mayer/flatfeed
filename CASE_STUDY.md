# FlatFeed Case Study

FlatFeed is a working Telegram prototype for reducing repeated checks across
Berlin WBS listings. The product concept is one four-criterion filter—WBS type,
district, maximum Kaltmiete and room count—followed by matching listings with
clear reasons in one consistent feed. A user can save that filter, request
matches and review the fixed-rule reasons before each result card. The catalog
is synthetic; the prototype does not demonstrate live source coverage or user
outcomes.

WBS (Wohnberechtigungsschein) is a certificate used to qualify for subsidized
housing in Berlin. Kaltmiete is the base rent, excluding operating and heating
costs.

## 1. Product Hypothesis

The premise: WBS users re-read fragmented listings and repeat the same basic
checks on each one. The implemented product is one saved filter followed by
on-demand matching listings in one consistent Telegram format. Its synthetic
catalog makes the interaction runnable without pretending to be a usable live
housing feed.

This portfolio prototype is complete at its intended scope. It demonstrates the
user experience and the bounded AI quality-control role without implying a
launched housing service.

## 2. Product and Role

The main path is:

```text
Save filter → Collect → Prepare → Match → Explain
```

- The user saves WBS type, district, maximum Kaltmiete, and rooms.
- A source adapter adds newly found listings to one catalog.
- Fixed rules normalize listing fields and estimate walks to the nearest S- and
  U-Bahn stations.
- Deterministic rules compare each listing with the saved criteria.
- The product explains each on-demand match and shows the canonical Telegram listing card.

I defined the WBS user problem and product scope; chose which fields determine
a match and how missing data is handled; set the AI boundary; and designed the
evaluation plan and acceptance criteria. I implemented the Telegram prototype
with Claude Code and Codex as coding collaborators.

## 3. Key Decisions

### A first-pass filter, not a final eligibility decision

I chose WBS type, district, maximum Kaltmiete, and rooms to reduce the listings
a user must review. FlatFeed uses them to create an initial shortlist; users
still verify complete eligibility and application details on the source page.

### Rules decide which listings appear

Parsing and matching follow fixed rules, so every result can be traced to the
saved filter. Separately, I evaluated a hosted model as an
admin-only parser check. That experiment is not integrated into the Telegram
runtime, and its findings cannot automatically change the listing or the match.

### One product flow across sources

Each permitted source would be normalized into the same listing format before
matching, so a future product could support one filter and one feed. The current
prototype exercises this design with one synthetic source and a working
saved-filter flow. Completeness and freshness across real sources are still untested,
and there is no live housing-company ingestion in this version.

## 4. Evidence and Limits

Implemented and evaluated:

- a user can save a four-field filter, request matches and see fixed-rule
  reasons before each synthetic listing card;
- Telegram listing summaries include estimated walks to the nearest S- and
  U-Bahn stations, calculated from synthetic coordinates in the demo;
- on 600 new synthetic listings, a hosted model plus deterministic comparison
  found and localized all 300 planted parser errors, raised no false alerts on
  300 clean listings, and returned 599 valid checks.

### Final AI QA evaluation

**AI QA evaluation · synthetic data · 600 listings**

FlatFeed uses deterministic rules to parse listings and match them to user
criteria. I evaluated a hosted model as a second check for admins: it compares
parsed data with source text and flags suspected errors. It does not change
listings or matching, and was not part of the user-facing product flow. The
final test used 600 synthetic listings: 300 clean listings and 300 listings
containing one planted parser error.

**Decision: passed the synthetic benchmark.**
The checker detected all 300 planted errors, raised no false alerts on 300
clean listings and returned a usable result for 599 of 600 checks. Every
predeclared gate passed.

Overall results show how reliably the checker worked across all 600 listings.
The breakdown below shows results for each piece of listing data—from WBS
eligibility and rent to address and floor. It makes sure a strong overall result
does not hide a weak spot.

| Overall metric | Final result | How it is calculated | Product focus | Prototype target |
|---|---:|---|---|---|
| Errors detected | 100.0% (300/300) | Corrupted listings that produced an alert ÷ 300 corrupted listings | Parser mistakes reaching admin review | At least 98% (294/300), met |
| False alerts | 0.0% (0/300) | Clean listings that produced an alert ÷ 300 clean listings | Unnecessary admin reviews | At most 1% (3/300), met |
| Correct data point identified | 100.0% (300/300) | Corrupted listings where the wrong data point was correctly identified ÷ 300 corrupted listings | Whether an alert tells an admin where to investigate | At least 98% (294/300), met |
| Usable AI responses | 99.8% (599/600) | Valid structured model responses ÷ 600 attempted checks | Whether the check completes in a usable form | At least 99.5% (597/600), met |

These thresholds were predeclared product acceptance criteria for this
prototype, not universal industry benchmarks.

The table shows results for every part of a listing. WBS, district, Kaltmiete,
and rooms affect matching; address, floor, and Warmmiete appear on the listing
card.

| Listing data | Used for | Errors found | Target | Result |
|---|---|---:|---:|---|
| WBS | Matching | 75/75 (100.0%) | At least 74/75 | Target met |
| District | Matching | 30/30 (100.0%) | 30/30 | Target met |
| Kaltmiete | Matching | 60/60 (100.0%) | At least 59/60 | Target met |
| Rooms | Matching | 50/50 (100.0%) | At least 49/50 | Target met |
| Address / postal code | Listing card | 40/40 (100.0%) | At least 39/40 | Target met |
| Floor | Listing card | 25/25 (100.0%) | 25/25 | Target met |
| Warmmiete | Listing card | 20/20 (100.0%) | 20/20 | Target met |

No planted parser error was missed. One clean listing failed the evidence-quote
validation, so the checker returned no usable decision for that listing. It did
not create a false alert and was not retried.

The final configuration used `gpt-5.6-terra` with high reasoning effort and
strict Structured Outputs. The model saw only raw listing text and returned
exact source quotes for eight values. Deterministic code compared those values
with the parser snapshot and created the single admin decision
`review_required`. The model did not change parsing, matching, or user-facing
listing summaries.

Within the prototype's planned budget for real-model testing, I used the final
benchmark once and kept its result unchanged.

> The final run met every synthetic acceptance gate, so I stopped synthetic
> tuning. The prototype is complete at its intended scope: a working
> saved-filter Telegram flow, deterministic matching and a bounded AI quality-control
> role.

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

Outside prototype scope:

- whether real WBS users adopt and trust the feed;
- whether permitted Berlin WBS sources can be combined into one complete,
  fresh feed;
- whether the feed reduces monitoring time and helps users act sooner;
- how often real source formats cause FlatFeed to miss a suitable listing;
- whether a real model tested on planted synthetic errors can detect naturally
  occurring parser errors in permitted live listings.

The evaluation used balanced synthetic cases, not live listings or natural
production error rates. The prototype has no permitted live dataset, so
accuracy on real listing formats and naturally occurring parser errors remains
unmeasured. Missing listings need a separate source-coverage check and are
outside this prototype.
