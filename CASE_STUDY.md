# FlatFeed Case Study

FlatFeed helps Berlin WBS users find matching apartments across housing
providers with one saved Telegram filter. A user sets their WBS tier,
preferred Berlin district, maximum Kaltmiete and room count once, then requests
matching apartments. With background delivery enabled, FlatFeed sends a
Telegram notification when a newly collected apartment matches that filter.

WBS (Wohnberechtigungsschein) is a certificate used to qualify for subsidized
housing in Berlin. Kaltmiete is the base rent, excluding operating and heating
costs.

## 1. Product Hypothesis

The premise: WBS users must repeatedly revisit housing-company websites, run
the same filters on each site, and manually compare listings across them.
FlatFeed turns that work into one saved filter, automatic notifications for new
matches and consistent Telegram listing cards.

The product combines a user-facing workflow, a multi-source ingestion
foundation and a bounded AI quality-control role.

## 2. Product and Role

The main path is:

```text
Save filter → Collect → Prepare → Match → Notify
```

- The user saves WBS type, district, maximum Kaltmiete, and rooms.
- Registered source adapters add listings to one normalized catalog.
- Fixed rules normalize listing fields and estimate walks to the nearest S- and
  U-Bahn stations.
- Deterministic rules compare each listing with the saved criteria.
- The product sends each new match once and shows the canonical Telegram listing card.

I defined the WBS user problem and product scope. I made timely notifications
part of the core flow so users can respond before a matching listing disappears.
I chose the matching fields, set the AI boundary, designed the evaluation
plan and acceptance criteria. I implemented the Telegram prototype with Claude
Code and Codex as coding collaborators.

## 3. Key Decisions

### A shortlist, not the final decision

Users choose their WBS type, district, maximum Kaltmiete and number of rooms.
FlatFeed shows apartments that match those preferences.

### Rules decide which listings appear

Parsing and matching follow fixed rules, so every result can be traced to the
saved filter. AI QA operates as a separate admin review layer: it can flag a
suspected parsing error, but it cannot automatically change the listing or the
match.

### One filter across all sources

FlatFeed converts listings from different housing providers into one format.
Users set one filter and receive the same Telegram cards, regardless of the
source.

## 4. What the prototype proves—and what still needs validation

This section shows how the Telegram bot works, how FlatFeed can add more listing
sources, and how well the AI checker performed on 600 synthetic listings.

What FlatFeed can already do:

- users can save a four-field filter, request matches and receive each newly
  collected matching listing once when background delivery is enabled;
- every Telegram card includes WBS eligibility, rent, apartment details and
  estimated walks to the nearest S- and U-Bahn stations;
- multiple source adapters can use the same collection flow, synchronize
  independently and receive activity and health checks;
- background notifications are deduplicated and tracked, so each match is sent
  once;
- runtime AI QA can flag possible parsing errors for private admin
  review but cannot change product data;
- on 600 new synthetic listings, a hosted model plus deterministic comparison
  found and localized all 300 planted parser errors, raised no false alerts on
  300 clean listings, and returned 599 valid checks.

### Final AI QA evaluation

**AI QA evaluation · synthetic data · 600 listings**

Parsing and matching stay rule-based. I ran hosted-model experiments to test AI
only as a second quality check for admins. The model read the raw listing and
returned exact source evidence; deterministic code compared it with the parser
output and flagged differences. The final test used 600 synthetic listings: 300
clean listings and 300 listings containing one planted parser error.

#### How I selected the setup

I increased model capability only when the previous setup missed a predefined
gate. I started with less expensive configurations and changed one variable at a
time. I moved to a more expensive setup only when a cheaper one missed criteria
defined before the run.

1. **Start with lower-cost settings.** I began with the lower-cost
   `gpt-5.6-Luna` model and compared no additional reasoning with low reasoning
   effort.
2. **Increase capability with evidence.** When those setups missed the
   acceptance gates, I moved to the stronger `gpt-5.6-Terra` model and compared
   none, low, medium and high reasoning effort on new datasets.
3. **Narrow the AI's job.** More model power alone was not enough. I limited AI
   to extracting exact source quotes and let fixed code make the comparison.
   The final Terra-high setup then met every predefined gate.

**Decision: passed the synthetic benchmark.**
The checker found all 300 planted errors, raised no false alerts on 300 clean
listings and returned a usable result for 599 of 600 checks. Every predeclared
prototype target passed.

An overall score can hide a weak spot. The breakdown below shows results for
every field used in matching or displayed on the Telegram card.

| Overall metric | Final result | How it is calculated | Product focus | Prototype target |
|---|---:|---|---|---|
| Errors detected | 100.0% (300/300) | Corrupted listings that produced an alert ÷ 300 corrupted listings | Parser mistakes reaching admin review | At least 98% (294/300), met |
| False alerts | 0.0% (0/300) | Clean listings that produced an alert ÷ 300 clean listings | Unnecessary admin reviews | At most 1% (3/300), met |
| Correct data point identified | 100.0% (300/300) | Corrupted listings where the wrong data point was correctly identified ÷ 300 corrupted listings | Whether an alert tells an admin where to investigate | At least 98% (294/300), met |
| Usable AI responses | 99.8% (599/600) | Valid structured model responses ÷ 600 attempted checks | Whether the check completes in a usable form | At least 99.5% (597/600), met |

These were acceptance criteria defined for this prototype before the final run,
not universal industry benchmarks.

WBS, district, Kaltmiete and rooms affect matching. Address, floor and
Warmmiete appear on the listing card. Every field met its target.

| Listing data | Used for | Errors found | Target | Result |
|---|---|---:|---:|---|
| WBS | Matching | 75/75 (100.0%) | At least 74/75 | Target met |
| District | Matching | 30/30 (100.0%) | 30/30 | Target met |
| Kaltmiete | Matching | 60/60 (100.0%) | At least 59/60 | Target met |
| Rooms | Matching | 50/50 (100.0%) | At least 49/50 | Target met |
| Address / postal code | Listing card | 40/40 (100.0%) | At least 39/40 | Target met |
| Floor | Listing card | 25/25 (100.0%) | 25/25 | Target met |
| Warmmiete | Listing card | 20/20 (100.0%) | 20/20 | Target met |

One clean listing produced no usable result because the model returned a quote
that did not appear exactly in the raw listing text. Local validation rejected
it. The check was not retried and did not create a false alert. It was the only
unusable result; no planted parser error was missed.

The final configuration used `gpt-5.6-Terra` with high reasoning effort and
strict Structured Outputs. The model read the original listing text and
returned quoted evidence for eight listing values. Fixed code compared that
evidence with FlatFeed's parsed data. If the two differed, it created one admin
task: `review_required`. This experiment ran offline and is not integrated into the product. It is separate from runtime AI QA and cannot change a listing,
decide a match or edit a Telegram card.

I ran the final 600-listing benchmark once within the planned budget and did
not tune the result afterwards.

> The final run met every synthetic acceptance gate, so I stopped synthetic
> tuning. The prototype is complete at its intended scope: a working
> saved-filter Telegram flow, deterministic matching and a bounded AI quality-control
> role. Performance on live provider data still needs separate validation.

### Estimated AI API cost at Berlin listing scale

The closest official volume reference is 12,398 apartment re-lettings reported
by six state-owned Berlin housing companies in 2024, excluding Berlinovo. This
is not a count of online ads. Because no consolidated count of unique listings
is public, I used a rounded planning scenario of 15,000 checks per year.

- **Measured run pattern:** about **$35 per year** or **$2.94 per month**:
  15,000 × $0.00235 per check. The final 600-check run cost `$1.412906`.
- **Planning case with a 25% buffer:** about **$45 per year** or **$3.68 per
  month**: 15,000 × $0.00294 per check.

This estimates AI API calls only, using one check per unique listing per prompt
version and prices recorded on 30 July 2026. It excludes source access, hosting,
monitoring, duplicate listings, price changes, differences in real-listing
length and human review. The 12,398 re-lettings indicate scale, not the exact
number of ads a live system would process.

Evidence:

- [Evaluation contract](eval/AI_QA_EVAL_PLAN.md)
- [Final 600-listing report](eval/runs/extraction-v1-final-600/report.md)
- [Official Berlin 2024 housing-company report announcement](https://www.berlin.de/sen/stadt/presse/pressemeldungen/pressemitteilung.1628093.php)

## 5. What this portfolio demo uses

The capabilities are implemented, but the demo runs in a controlled setup:

- the multi-source ingestion layer is implemented, with FlatFeed Synthetic as
  the only enabled adapter; the demo does not scrape housing-provider websites;
- users can request matches on demand; automatic notifications work when
  `BOT_BACKGROUND_ENABLED=true`, while this demo keeps the switch off;
- runtime AI QA for admins is implemented but disabled;
- the accepted hosted-model configuration was evaluated offline, is not part of
  the user-facing product flow and is not connected to Telegram;
- the showcase photo, address, district and coordinates refer to Schlangenbader
  Straße 91; apartment availability, rent, floor, rooms and WBS eligibility are
  synthetic.

Still needs real-world validation:

- whether real Berlin WBS users adopt and trust the product;
- how complete and up to date permitted housing-provider sources would be;
- how often real source formats cause FlatFeed to miss a suitable listing;
- whether the accepted offline model configuration can detect naturally
  occurring parser errors in permitted live listings;
- whether the product reduces monitoring time and helps users respond faster.

The evaluation used balanced synthetic cases, not live listings or natural
production error rates. The prototype has no permitted live dataset, so
accuracy on real listing formats and naturally occurring parser errors remains
unmeasured. Missing listings need a separate source-coverage check and are
outside this prototype. Before production, every AI alert and an independent
random sample of listings receiving no alert would still require human review.
