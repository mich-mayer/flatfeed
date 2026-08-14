# FlatFeed Case Study

# Berlin WBS apartment seekers repeat the same search across multiple websites.

WBS (Wohnberechtigungsschein) is a certificate used to qualify for subsidized
housing in Berlin.

Several property portals let users save searches and receive alerts, but each
alert covers only its own platform. Housing providers also publish apartments
on their own websites. Users therefore repeat the same WBS, district, rent and
room search across several places and compare different listing formats.
FlatFeed tests a simpler flow: save those criteria once and review matching
listings in Telegram.

**Product:** Working Telegram prototype · Generated test listings · Rule-based
matching

**Evaluation:** AI extracts source evidence; code checks it · Tested offline on
600 synthetic listings

**Project ownership:** I defined the problem and scope, chose how matching
works, decided where AI should and should not be used and set the evaluation
targets.

## 1. Problem

Several property portals offer saved-search alerts, but each alert covers only
listings on that platform. Housing providers also publish apartments on their
own websites. Users therefore repeat the same eligibility, district, rent and
room criteria across several places and compare different listing formats
before they can respond. The need is based on first-hand and observed
experience; the prototype does not claim a measured market prevalence or user
outcome.

## 2. Product

### Users can save one filter and review matching listings in Telegram.

Users save WBS type, district, maximum Kaltmiete and rooms. Kaltmiete is the
base rent, excluding operating and heating costs. FlatFeed puts every listing
into the same format, checks it against the saved filter with fixed rules and
returns matches in a Telegram card.

1. **Save one filter.** Set the four matching criteria once.
2. **Put listings into one format.** One import flow turns every listing into
   the same set of fields. The demo uses one synthetic source adapter and
   includes no live provider adapters.
3. **Match with rules.** Code compares each listing with the saved criteria. If
   required rent or room data is missing, the listing does not match.
4. **Return each new match once.** Users can request matches when they want.
   Background delivery can send new matches and record each successful send to
   prevent duplicates. It is built but switched off in this demo.

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

### I made three decisions to keep the product focused and testable.

This was a self-directed portfolio project, not a live rollout. I made the
product and evaluation decisions and implemented the prototype with Claude Code
and Codex as coding collaborators.

1. **Do not match a listing when required data is missing.** If rent or room
   count is missing, the listing does not match a filter that requires it. This
   reduces wrong matches but may hide a suitable listing. Real data is needed
   to judge the trade-off.
2. **Do not promise coverage before source access is clear.** The demo uses
   generated listings through one synthetic source adapter. I have not validated
   access to provider websites or the terms for using their listings, so the
   prototype does not claim to cover live listings.
3. **Give AI a narrow, checkable task.** AI alone sometimes missed conflicts
   between a listing and the parsed data. Adding more prompt rules improved one
   field but made others worse. I therefore asked AI only to quote the source
   and let code compare the values.

**User path:** Saved filter → Rule-based matching → Telegram result

**Offline evaluation path:** Listing text → AI returns an exact quote or `null`
→ Code checks the quote and compares values → Result marked for offline review

The tested setup ran offline. It cannot change listing data, decide matches or
affect the Telegram product.

## 4. AI Evaluation

### The product works with generated listings. A separate AI quality check passed its 600-listing synthetic test.

The seven Telegram screens above show the working product. A separate offline
test asked whether AI and code could find deliberately planted errors in data
extracted from listings.

**AI QA evaluation · synthetic data · 600 listings**

I fixed the final dataset before the run: 300 clean listings and 300 with one
planted parser error. The model saw only raw listing text. It did not see the
expected answers, FlatFeed's parsed values or labels identifying each test
case. The test ran once, with no retries, tuning or rescoring afterward.

**Passed the synthetic benchmark. Every predeclared prototype target passed.**

| Metric | Result | Prototype target |
|---|---:|---:|
| Errors detected | 100.0% (300/300) | At least 98% (294/300) |
| Unnecessary review flags | 0.0% (0/300) | At most 1% (3/300) |
| Correct field identified | 100.0% (300/300) | At least 98% (294/300) |
| Usable results | 99.8% (599/600) | At least 99.5% (597/600) |

I set these acceptance criteria before the final run. They apply to this
prototype, not to the industry as a whole.

One clean listing produced an unusable quote. Code rejected it because the
quote was not present in the listing, so it created no unnecessary review flag.
This demonstrates feasibility on controlled synthetic data—not live-source
accuracy, production performance or user impact. The tested setup ran offline
and is not integrated into the product.

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

Before using AI quality checks on real listings, reviewers should inspect every
flagged case and a random sample of listings with no flag.

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

I turned a repeated housing search into a working Telegram prototype. I used
rules to decide which listings match, kept AI in a separate data-quality check
and defined what must be validated before testing with real listings.

## Another case

Opsqora uses AI differently: AI groups support feedback while people decide
what to build.

[Read the case study →](https://mich-mayer.github.io/opsqora/case-study.html)
