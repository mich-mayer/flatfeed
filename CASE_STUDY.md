# FlatFeed Case Study

# Berlin WBS apartment seekers repeat the same search across multiple websites.

WBS (Wohnberechtigungsschein) is a certificate used to qualify for subsidized
housing in Berlin.

Several real-estate portals let users save searches and receive alerts, but each
alert covers only its own platform. Meanwhile, housing providers are a primary source of
WBS listings and may publish them on their own websites before they reach
real-estate portals. Some providers offer only email alerts; others offer none.
Users therefore repeat the same search across several places and compare
different listing formats. FlatFeed tests a simpler flow: save your criteria
once and review matching listings in Telegram.

## 1. Problem

Several real-estate portals offer saved-search alerts, but each alert covers only
listings on that platform. Meanwhile, housing providers are a primary source of WBS
listings and may publish them on their own websites before they reach property
portals. Some providers offer only email alerts; others offer none. Users
therefore repeat searches across several places and compare different listing
formats before they can respond. The need is based on first-hand and observed
experience; the prototype does not claim a measured market prevalence or user
outcome.

## 2. Product

### Users can save one filter and review matching listings in Telegram.

Working Telegram prototype · Generated test listings · Rule-based matching · AI parser-quality review

1. **Save one filter.** Set WBS type, district, maximum Kaltmiete (base rent,
   excluding operating and heating costs) and rooms once.
2. **Turn listing text into structured fields.** The parser extracts WBS,
   district, rent, rooms and the details shown on each card. Every matching rule
   and Telegram result depends on these fields. The demo uses one synthetic
   source adapter and includes no live provider adapters.
3. **Match with rules.** Code compares each listing with the saved criteria. If
   required rent or room data is missing, the listing does not match.
4. **Return matches in Telegram.** Users can request matches when they
   want. FlatFeed returns each match in a Telegram card. Background delivery
   can send new matches and record each successful send to prevent duplicates.

Seven captured Telegram screens document the implemented journey:

1. Open filter setup.
2. Choose WBS type.
3. Choose a district.
4. Set maximum Kaltmiete.
5. Choose room count.
6. Review the saved filter.
7. Review a matched listing in one consistent card.

The final screen uses a photo by Bodo Kubrak under CC0 1.0; the local copy was
resized. The location is Schlangenbader Straße 91. Apartment details are
synthetic.

## 3. Decisions

### Three decisions kept the prototype focused and testable.

**My role**

I defined the WBS user problem and product scope; chose which fields determine
a match and how missing data is handled; set the AI boundary; and designed the
evaluation plan and acceptance criteria. I then implemented the Telegram
prototype with Claude Code and Codex as coding collaborators.

Self-directed portfolio project · Not a live rollout

1. **Use AI to audit the parser—not to decide matches.** Deterministic rules
   still depend on correct input data. I tested whether AI could act as an
   independent parser check: it returned exact source evidence for each
   requested field, while code compared that evidence with simulated parser
   output. Differences were marked for review; AI never changed listing data or
   match decisions.
2. **Use synthetic data to test mechanics.** I chose generated listings to
   test filter setup, normalization, matching and Telegram delivery without
   using provider data until source access and reuse terms are clear. This tests
   product mechanics, but not source coverage, listing freshness or renter
   value; those require permitted live sources and a real-user pilot.
3. **Fail closed when critical data is missing.** If rent or room count required
   by a filter is unknown, the listing does not match. This reduces unsupported
   matches but may hide a suitable apartment, so the trade-off still needs
   real-world validation.

## 4. AI Evaluation

### Correct matching starts with correct data.

FlatFeed’s rules depend on the fields produced by the parser. A wrong WBS, rent
or room value can hide a suitable listing or show one that does not match the
saved filter. I tested AI as an independent check: it returned exact source
evidence for each field, and code compared that evidence with simulated parser
output. The benchmark used generated listings, ran offline and never changed
Telegram results.

### Can AI and code detect field-level data conflicts?

I froze the final synthetic dataset before the run: 300 text–data pairs that
agreed and 300 with one deliberately altered structured value. The model saw
only the generated listing text. It did not see the structured values or labels
identifying each test case. Code then compared the model’s quoted evidence with
those values. The test ran once, with no retries, tuning or rescoring afterward.

| Metric | Result | Prototype target |
|---|---:|---:|
| Errors detected | 100.0% (300/300) | At least 98% (294/300) |
| Unnecessary review flags | 0.0% (0/300) | At most 1% (3/300) |
| Correct field identified | 100.0% (300/300) | At least 98% (294/300) |
| Usable results | 99.8% (599/600) | At least 99.5% (597/600) |

I set these acceptance criteria before the final run. They apply to this
prototype, not to the industry as a whole.

**Evidence boundary**

One clean listing produced an unusable quote. Code rejected it because the
quote was not present in the listing, so it created no unnecessary review flag.
This demonstrates feasibility on controlled synthetic data—not live-source
accuracy, production performance or user impact. The tested setup ran offline
and is not integrated into the product.

Controlled synthetic evaluation · Offline · Not integrated into the product

### Evaluation method and field-level results

The final setup used `gpt-5.6-terra` with high reasoning effort and a strict
response format (Structured Outputs). For each field, the model returned an
exact quote from the listing or `null`. Code rejected invalid output, compared
the quoted evidence with FlatFeed's parsed value and marked any difference for
offline review.

The only unusable result contained a quote that was not in the listing. The
case was not retried. No planted parser error was missed.

| Listing data | Used for | Errors found | Prototype target |
|---|---|---:|---:|
| WBS | Matching | 75/75 · 100.0% | At least 74/75 |
| District | Matching | 30/30 · 100.0% | 30/30 |
| Kaltmiete | Matching | 60/60 · 100.0% | At least 59/60 |
| Rooms | Matching | 50/50 · 100.0% | At least 49/50 |
| Address / postal code | Listing card | 40/40 · 100.0% | At least 39/40 |
| Floor | Listing card | 25/25 · 100.0% | 25/25 |
| Warmmiete | Listing card | 20/20 · 100.0% | 20/20 |

### Cost assumptions

The final 600-check run cost `$1.412906`, or `$0.00235` per attempted check.

At a planning volume of 15,000 checks per year, the measured cost pattern would
be about `$35` per year (`$2.94` per month). A 25% planning buffer produces
`$0.00294` per check, about `$45` per year (`$3.68` per month).

The 15,000-check figure is a planning scenario, not a forecast. Berlin reported
12,398 apartment re-lettings by six state-owned housing companies in 2024,
excluding Berlinovo. This is not the number of online ads.

The estimate covers AI API calls only. It excludes source access, hosting,
monitoring, duplicate listings, price changes, differences in real-listing
length and human review. It uses prices recorded on 30 July 2026.

Evidence:

- [Evaluation plan](eval/AI_QA_EVAL_PLAN.md)
- [Final 600-listing report](eval/runs/extraction-v1-final-600/report.md)
- [Repository](https://github.com/mich-mayer/flatfeed)
- [Berlin volume reference](https://www.berlin.de/sen/stadt/presse/pressemeldungen/pressemitteilung.1628093.php)

## 5. Next

### The next evidence should come from real alerts, not another model benchmark.

The next step is to confirm which sources permit this use and then test whether
the resulting alerts are timely and useful.

- **Source coverage:** How many listings are available from permitted sources?
- **Time to alert:** How long after publication does an alert arrive?
- **Alert follow-through:** What share of alerts do users open or act on?
- **Irrelevant or unavailable listings:** What share of alerts are irrelevant
  or already unavailable?

### Data-quality gate for live listings

Before relying on parsed data from permitted sources, reviewers should verify
WBS, district, rent, rooms and card fields on a random sample of listings.
Every AI flag and a random sample of unflagged listings should be reviewed to
measure both detected errors and missed errors.

Before live-source reliance · Human review required

Current prototype limits:

- The demo uses one synthetic source adapter and includes no live provider
  adapters.
- On-demand matching works. Automatic background delivery with duplicate
  prevention is built but switched off in the demo.
- An optional AI quality check for administrators is built but switched off.
  The model setup reported above was tested separately offline and is connected
  to neither that path nor the Telegram product.
- Live-source performance and user impact have not been measured.

## What this demonstrates

### A working product, clear decisions and evidence for the next step.

I built a rule-based Telegram product and tested AI as an independent
parser-quality control. Rules decide matches; AI supplies field-level evidence
for data review. Real-source accuracy and user value remain the next validation
step.

## Another case

Opsqora uses AI differently: AI groups support feedback while people decide
what to build.

[Read the case study →](https://mich-mayer.github.io/opsqora/case-study.html)
