# FlatFeed Case Study

# Berlin WBS apartment seekers repeat the same search across multiple websites.

WBS (Wohnberechtigungsschein) is a certificate used to qualify for subsidized
housing in Berlin.

Portal alerts cover only listings on that platform. Housing providers also
publish apartments on their own websites, so users repeat the same WBS,
district, rent and room search across several places and compare different
listing formats. The FlatFeed prototype tests a simpler flow: save those
criteria once and review matching listings in Telegram.

**Product:** Working Telegram prototype · Generated test listings · Rule-based
matching

**Evaluation:** Separate AI-and-code data-quality check · Tested offline on 600
synthetic listings

**Project ownership:** I defined the problem and product scope, chose the
matching rules and AI role, made the implementation decisions and set the
evaluation targets.

## 1. Problem

Portal alerts do not cover apartments that providers publish only on their own
websites. Users repeat the same eligibility, district, rent and room criteria
and then compare different listing formats before they can respond. The need is
based on first-hand and observed experience; the prototype does not claim a
measured market prevalence or user outcome.

## 2. Product

### A complete saved-filter journey works in Telegram.

Users save WBS type, district, maximum Kaltmiete and rooms. Kaltmiete is the
base rent, excluding operating and heating costs. FlatFeed maps listings into
one consistent format, compares them with the saved filter using deterministic
rules and returns matches in a Telegram card.

1. **Save one filter.** Set the four matching criteria once.
2. **Normalize listings.** A shared import pipeline maps each listing into one
   schema. The demo uses one synthetic adapter; no live provider adapters are
   included.
3. **Match with rules.** Deterministic code compares each listing with the
   saved criteria. Missing required rent or room data does not count as a match.
4. **Return each new match once.** Users can request matches on demand.
   Background delivery with duplicate prevention is implemented but disabled
   in this demo.

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

### Three decisions defined the product boundary.

This was a self-directed portfolio project, not a live rollout. I made the
product and evaluation decisions and implemented the prototype with Claude Code
and Codex as coding collaborators.

1. **Missing required values do not count as matches.** When a filter requires
   rent or room count and the listing lacks that value, FlatFeed does not treat
   it as a match. This avoids unsupported matches but may hide a suitable
   listing; the trade-off still needs live validation.
2. **Do not claim coverage before validating source access.** The demo uses
   generated listings through one synthetic adapter. I have not validated
   access to provider websites or the terms for using their listings, so the
   prototype makes no live-coverage claim.
3. **Give AI a narrow, checkable task.** A model-only comparison missed direct
   contradictions. Additional prompt rules improved one field but degraded
   others, so I narrowed the task: extract exact source evidence, then let
   deterministic code validate and compare it.

**User path:** Saved filter → Rule-based matching → Telegram result

**Offline evaluation path:** Raw listing text → AI extracts a source quote or
`null` → Code validates and compares parsed values → Offline review-required
result

The evaluated AI-and-code setup ran offline. It cannot change listings, decide
matches or affect the Telegram flow.

## 4. AI Evaluation

### The product works with generated listings. The data-quality check passed its synthetic benchmark.

Seven Telegram screens document the implemented journey. A separate offline
evaluation tested whether a bounded AI-and-code check could detect deliberately
planted parser errors.

**AI QA evaluation · synthetic data · 600 listings**

The final dataset was fixed before the run: 300 clean listings and 300 with one
planted parser error. The model saw raw listing text only—not expected answers,
parser snapshots or labels identifying the test case. The benchmark ran once,
with zero retries and no post-run tuning or rescoring.

**Passed the synthetic benchmark. Every predeclared prototype target passed.**

| Metric | Result | Prototype target |
|---|---:|---:|
| Errors detected | 100.0% (300/300) | At least 98% (294/300) |
| Unnecessary review flags | 0.0% (0/300) | At most 1% (3/300) |
| Correct field identified | 100.0% (300/300) | At least 98% (294/300) |
| Usable results | 99.8% (599/600) | At least 99.5% (597/600) |

These acceptance criteria were defined for this prototype before the final
run; they are not universal industry benchmarks.

One clean listing produced an unusable quote. Local validation rejected it, and
no unnecessary review flag was created. This demonstrates feasibility on controlled synthetic data—not live-source accuracy, production performance or
user impact. The evaluated configuration ran offline and is not integrated into the product.

### Evaluation method and field-level results

The final configuration used `gpt-5.6-terra` with high reasoning effort and
strict Structured Outputs. For every evaluated value, the model returned an
exact source quote or `null`. Deterministic code validated the output, compared
it with FlatFeed's parsed values and produced the offline outcome
`review_required` when values differed.

The only unusable result contained a quote that did not appear exactly in the
raw listing text. The case was not retried, and no planted parser error was
missed.

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

The 15,000-check figure is a planning scenario, not a forecast. The closest
official volume reference is 12,398 apartment re-lettings reported by six
state-owned Berlin housing companies in 2024, excluding Berlinovo. Re-lettings
are not the same as online advertisements.

The estimate covers AI API calls only. It excludes source access, hosting,
monitoring, duplicate listings, price changes, differences in real-listing
length and human review. Prices were recorded on 30 July 2026.

Evidence:

- [Evaluation contract](eval/AI_QA_EVAL_PLAN.md)
- [Final 600-listing report](eval/runs/extraction-v1-final-600/report.md)
- [Repository](https://github.com/mich-mayer/flatfeed)
- [Berlin volume reference](https://www.berlin.de/sen/stadt/presse/pressemeldungen/pressemitteilung.1628093.php)

## 5. Next

### The next evidence should come from real alerts, not another model benchmark.

The next step is to confirm which sources permit this use and then test whether
the resulting alerts are timely and useful.

- **Source coverage:** How many listings are available from permitted sources?
- **Time to alert:** How long does publication-to-notification take?
- **Alert follow-through:** What share of notifications do users open or act on?
- **Irrelevant or unavailable listings:** What share does not fit the user's
  needs or is already unavailable?

Before testing AI data-quality checks with real listings, reviewers should
inspect every review flag and an independent random sample of listings without
flags.

Current prototype limits:

- One synthetic adapter is present and enabled; no live provider adapters are
  included.
- On-demand matching works. Background delivery with duplicate prevention is
  implemented but disabled in the demo.
- An optional runtime admin-QA path is implemented but disabled. The accepted
  hosted-model configuration was evaluated separately offline and is connected
  to neither that path nor the Telegram flow.
- Live-source performance and user impact have not been measured.

## What this demonstrates

### A working product, clear decisions and evidence for the next step.

I turned a repeated housing search into a working Telegram prototype. I used
rules to decide which listings match, kept AI in a separate data-quality check
and defined what must be validated before testing with real listings.

## Another case

Opsqora explores a different AI boundary: AI groups support feedback while
people decide what to build.

[Read the case study →](https://mich-mayer.github.io/opsqora/case-study.html)
