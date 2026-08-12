# FlatFeed Case Study

FlatFeed helps Berlin WBS users avoid repeatedly checking several
housing-provider websites for new apartments. Users save their WBS type,
preferred Berlin district, maximum Kaltmiete and room count once. FlatFeed
checks newly collected listings against that filter and sends a Telegram
notification when a matching apartment appears.

WBS (Wohnberechtigungsschein) is a certificate used to qualify for subsidized
housing in Berlin. Kaltmiete is the base rent, excluding operating and heating
costs.

## 1. Problem

New WBS listings can appear and disappear quickly. Checking several provider
websites again and again takes time, repeats the same work and makes it easy to
see a suitable apartment too late. FlatFeed replaces that repeated monitoring
with one saved filter, timely Telegram notifications and one consistent listing
format.

## 2. Solution

Users save WBS type, district, maximum Kaltmiete and rooms once. FlatFeed
prepares listings from different sources in one format, compares them with the
saved criteria and sends a Telegram notification when a newly collected
apartment matches.

```text
Save one filter → Prepare every source → Match with rules → Notify once
```

1. **Save one filter.** Users set the four criteria once instead of repeating
   them on every housing-provider website.
2. **Prepare every source.** Source adapters convert different provider formats
   into one shared listing schema.
3. **Match with rules.** Deterministic code compares each listing with the saved
   criteria.
4. **Notify once.** Each newly collected match is verified, sent to Telegram
   and recorded to prevent duplicates.

Without FlatFeed, users repeatedly check several sites, enter the same criteria
and manually compare results before a suitable listing disappears. With
FlatFeed, they set one filter, receive a matching alert and review every listing
in one consistent format.

## 3. What I Built

The Telegram product supports the complete saved-filter journey:

- create and edit a filter with WBS type, district, maximum Kaltmiete and rooms;
- request matching listings on demand;
- receive automatic notifications for newly collected matching listings;
- review WBS eligibility, rent, apartment details and estimated walks to the
  nearest S-Bahn and U-Bahn stations in one consistent card;
- reset the saved filter or delete stored product data.

No separate explanation message follows a listing. The listing card is the
complete user-facing result.

The system foundation includes:

- a shared contract for multiple source adapters;
- independent source synchronization, activity checks and health checks;
- one normalized listing schema;
- deterministic parsing and matching;
- notification tracking and deduplication.

The HTML case study uses seven Telegram captures to show the product without
opening a live prototype: start, WBS type, district, maximum Kaltmiete, rooms,
saved filter and matching listing. The final capture includes a building photo
by Bodo Kubrak, CC0 1.0; the local copy was resized and the location is
Schlangenbader Straße 91.

## 4. My Role

I defined the WBS user problem and product scope. I made timely notifications
part of the core flow because repeatedly monitoring several sites takes time
and a late discovery can leave too little time to respond. I chose the four
matching fields, shaped the shared source-adapter architecture, set the
boundary between fixed rules and AI, and designed the evaluation plan and
acceptance criteria.

I implemented the Telegram prototype with Claude Code and Codex as coding
collaborators. This was a self-directed portfolio project; I owned the product,
evaluation and implementation decisions directly rather than managing an ML
team or a live rollout.

## 5. How AI Fits

AI is not used to decide which apartments users see. WBS type, district,
maximum Kaltmiete and rooms are explicit criteria, so deterministic rules are
more predictable and easier to trace.

AI is useful as a second data-quality check because provider listings express
the same values in different language and layouts. The model rereads the
original listing, extracts exact source evidence and can create a private admin
review task when that evidence differs from the parser output. It cannot change
a listing, decide whether it matches or edit a Telegram card.

The user product and the admin quality path stay separate. Fixed code owns
listing data and matching. AI can point admins to a possible parser
discrepancy, but it does not control the user experience.

### How I selected the AI QA setup

I started with lower-cost settings and moved to a stronger configuration only
when the previous one missed acceptance criteria defined before the run.

1. **Start with lower-cost settings.** I began with `gpt-5.6-Luna` and compared
   no additional reasoning with low reasoning effort.
2. **Increase capability with evidence.** When Luna missed the gates, I moved
   to `gpt-5.6-Terra` and compared none, low, medium and high reasoning effort
   on new datasets.
3. **Narrow the AI's job.** More model power alone was not enough. I limited AI
   to extracting exact source quotes and let fixed code compare them. The final
   Terra-high setup met every predefined gate.

## 6. Results

### Implemented product

The end-to-end Telegram flow and multi-source foundation are implemented. User
impact is not measured yet.

### Measured AI QA experiment — synthetic data

**AI QA evaluation · synthetic data · 600 listings**

Parsing and matching stay rule-based. I evaluated AI only as a second quality
check for admins. The model reread the original listing and returned exact
source quotes; fixed code compared them with the parsed values. The final test
used 600 synthetic listings: 300 clean listings and 300 listings containing one
planted parser error.

**Decision: passed the synthetic benchmark.**
The checker found all 300 planted errors, raised no false alerts on 300 clean
listings and returned a usable result for 599 of 600 checks. Every predeclared
prototype target passed.

| Overall metric | Final result | How it is calculated | Product focus | Prototype target |
|---|---:|---|---|---|
| Errors detected | 100.0% (300/300) | Corrupted listings that produced an alert ÷ 300 corrupted listings | Parser mistakes reaching admin review | At least 98% (294/300), met |
| False alerts | 0.0% (0/300) | Clean listings that produced an alert ÷ 300 clean listings | Unnecessary admin reviews | At most 1% (3/300), met |
| Correct data point identified | 100.0% (300/300) | Corrupted listings where the wrong data point was correctly identified ÷ 300 corrupted listings | Whether an alert tells an admin where to investigate | At least 98% (294/300), met |
| Usable AI responses | 99.8% (599/600) | Valid structured model responses ÷ 600 attempted checks | Whether the check completes in a usable form | At least 99.5% (597/600), met |

These criteria were defined before the final run. They are synthetic prototype
metrics, not universal industry benchmarks, production performance or user
impact.

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
that did not appear exactly in the original listing text. Local validation
rejected it. The check was not retried and did not create a false alert. No
planted parser error was missed.

The final configuration used `gpt-5.6-Terra` with high reasoning effort and
strict Structured Outputs. The model returned quoted evidence for eight listing
values. Fixed code compared that evidence with FlatFeed's parsed data and could
create one admin task: `review_required`.

This experiment ran offline and is not integrated into the product. It cannot
change a listing, decide a match or edit a Telegram card. I ran the final
600-listing benchmark once within the planned budget and did not tune the
result afterwards.

> The final run met every synthetic acceptance gate, so I stopped synthetic
> tuning. The prototype is complete at its intended scope: an implemented
> Telegram flow, deterministic matching and a bounded AI quality-control role.
> Performance on live provider data still needs separate validation.

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

## 7. What I Learned

### Rules are better for explicit criteria

WBS type, district, rent and rooms do not need model judgment. Fixed matching
is cheaper, traceable and predictable.

### Model power was only part of the answer

The accepted result required both a stronger configuration and a narrower
task: extract source evidence, then let fixed code compare it.

### Synthetic success has a clear limit

The benchmark shows controlled feasibility. It does not prove live-source
coverage, natural parser-error rates or user impact.

### What I would test next

If I continued the project, I would validate permitted live-source access and
alert usefulness before expanding the AI system. The next product evidence
would measure source coverage, time from a listing appearing to an alert being
delivered, acted-on notifications and the rate of irrelevant or unavailable
matches. The next question is whether FlatFeed helps users find suitable
listings faster, not whether a larger model can improve a synthetic benchmark.

### Current limits

The capabilities are implemented, but the portfolio demo runs in a controlled
setup:

- the multi-source ingestion layer is implemented, with FlatFeed Synthetic as
  the only enabled adapter; the demo does not scrape housing-provider websites;
- users can request matches on demand; automatic notifications work when
  `BOT_BACKGROUND_ENABLED=true`, while this demo keeps the switch off;
- runtime AI QA for admins is implemented but disabled;
- the accepted hosted-model configuration was evaluated offline, is not part of
  the user-facing product flow and is not connected to Telegram;
- the showcase photo, address, district and coordinates refer to Schlangenbader
  Straße 91; the building photo is by Bodo Kubrak, CC0 1.0, and the local copy
  was resized; availability, rent, floor, rooms and WBS eligibility are
  synthetic.

Still needs real-world validation:

- whether real Berlin WBS users adopt and trust the product;
- how complete and up to date permitted housing-provider sources would be;
- how often real source formats cause FlatFeed to miss a suitable listing;
- whether the accepted offline model configuration can detect naturally
  occurring parser errors in permitted live listings;
- whether the product reduces monitoring time and helps users respond faster.

The evaluation used balanced synthetic cases, not live listings or natural
production error rates. Before production, every AI alert and an independent
random sample of listings receiving no alert would still require human review.

One filter. Timely apartment alerts. FlatFeed brings multiple listing sources
into one flow, matches apartments with fixed rules and uses AI to check data
quality.
