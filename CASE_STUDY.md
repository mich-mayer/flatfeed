# FlatFeed Case Study

# Berlin WBS apartment seekers repeat the same search across multiple websites.

WBS (Wohnberechtigungsschein) is a certificate used to qualify for subsidized
housing in Berlin.

Saved-search alerts on real-estate portals only cover listings published on their
own platforms. Meanwhile, housing providers are a primary source of
WBS listings and may publish them on their own websites before they reach
real-estate portals. Some providers offer only email alerts; others offer none.
Users therefore repeat the same search across several places and compare
different listing formats. FlatFeed tests a simpler flow: save your criteria
once and review matching listings in Telegram.

## 1. Problem

Saved-search alerts on real-estate portals only cover listings published on their
own platforms. Meanwhile, housing providers are a primary source of WBS
listings and may publish them on their own websites before they reach property
portals. Some providers offer only email alerts; others offer none. Users
therefore repeat searches across several places and compare different listing
formats before they can respond. The need is based on first-hand and observed
experience; the prototype does not claim a measured market prevalence or user
outcome.

## 2. Product

### FlatFeed brings the fragmented WBS search together in one place.

Working Telegram prototype · Generated test listings · Rule-based matching · Bounded AI QA evaluation

1. **Save one filter.** Set WBS type, district, maximum Kaltmiete (base rent,
   excluding operating and heating costs) and rooms once.
2. **Normalize each source into one listing format.** Each permitted source
   would map into the same listing format. Structured feeds can supply fields
   directly; text-based or incomplete sources require extraction. This
   prototype implements the text-based path.
3. **Match with rules.** Code compares each listing with the saved criteria. If
   a required value is missing, the listing does not match.
4. **Return matches in Telegram.** Users can request matches when they
   want. FlatFeed returns each match in a Telegram card. After a user saves a
   filter, FlatFeed automatically sends each new match in Telegram and records
   each successful send to prevent duplicates.

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

### Current prototype limits

- The prototype currently uses generated listing text rather than live provider
  data. It implements one possible ingestion path: deterministic extraction
  into a common listing format with an admin-only AI quality check.
- How listings reach FlatFeed in production depends on the access method, data
  format and information each provider supplies. Complete structured feeds can
  be added directly; text-based or incomplete sources may still need extraction
  and review.
- Automatic delivery and the runtime AI check are built but disabled in this
  prototype. The AI-check results come from an offline evaluation using
  synthetic listing data, not listing data from real providers.

## 3. Decisions

### Three decisions kept the prototype focused and testable.

**My role**

I defined the WBS user problem and product scope; chose which fields determine
a match and how missing data is handled; set the AI boundary; and designed the
evaluation plan and acceptance criteria. I then implemented the Telegram
prototype with Claude Code and Codex as coding collaborators.

1. **Evaluate AI as a conditional quality check.** For this self-directed
   portfolio project, I deliberately tested one plausible text-based ingestion
   path to demonstrate how I scope, evaluate and constrain AI. The model checks
   parser evidence but never changes listings or decides matches. If a provider
   supplies complete, reliable structured fields, its adapter should map them
   directly; the parser and AI check are used only where extraction is actually
   needed.
2. **Use synthetic data to test mechanics.** I chose generated listings to
   test filter setup, normalization, matching and Telegram delivery without
   using provider data until source access and reuse terms are clear. This tests
   product mechanics, but not source coverage, listing freshness or renter
   value; those require permitted live sources and a real-user pilot.
3. **Do not match listings when required details are missing.** If rent or room
   count required by a filter is unknown, the listing does not match. This
   reduces unsupported matches but may hide a suitable apartment, so the
   trade-off still needs real-world validation.

## 4. AI Evaluation

### For text-based sources, correct matching starts with correct extraction.

This evaluation covers the prototype's text-based ingestion path. AI
independently checks the fields extracted by the parser and flags differences
for admin review; rules still decide every match. A provider feed with complete,
reliable structured fields could bypass this path.

### How the check catches a wrong value.

| Source | Values |
| --- | --- |
| **Listing text** | *Charlottenburg-Wilmersdorf · 2 Zimmer · 512,40 € · WBS 100–140.* |
| **Parser output** | `WBS 140` · `Charlottenburg-Wilmersdorf` · `€512.40` · `2` |
| **AI evidence** | `WBS 100–140` · `Charlottenburg-Wilmersdorf` · `€512.40` · `2` |

**Mismatch detected.** The parser missed WBS 100 and could hide a suitable
listing. **Admin review required.** AI flags the difference and stops there. A
configured admin compares the original listing and marks the finding as parser
error, parser correct or unsure. Nothing changes on the model's word alone.

### But how well can the check flag parser errors?

Before testing any model setups, I defined the metric targets. I then compared
model setups on separate development data. `gpt-5.6-terra` with high reasoning
met those targets, so I froze the setup before running it once on the locked
600-listing evaluation. FlatFeed already includes an admin-only AI check that
asks a model for source evidence and compares it with parser output.
To test one model configuration for that check, I ran it once on 600 synthetic
listing pairs: 300 clean and 300 with one planted parser error. For each field,
the model returned an exact source quote or no value, and code checked it
against the parser output. There were no retries or tuning after the run.

| Metric | Result | Prototype target |
|---|---:|---:|
| Errors detected | 100.0% (300/300) | At least 98% (294/300) |
| Unnecessary review flags | 0.0% (0/300) | At most 1% (3/300) |
| Correct field identified | 100.0% (300/300) | At least 98% (294/300) |
| Usable results | 99.8% (599/600) | At least 99.5% (597/600) |

### Field-level results

| Listing data | Used in | Errors found | Prototype target |
|---|---|---:|---:|
| WBS | Matching + Telegram card | 75/75 · 100.0% | At least 74/75 |
| District | Matching + Telegram card | 30/30 · 100.0% | 30/30 |
| Kaltmiete | Matching + Telegram card | 60/60 · 100.0% | At least 59/60 |
| Rooms | Matching + Telegram card | 50/50 · 100.0% | At least 49/50 |
| Address / postal code | Telegram card | 40/40 · 100.0% | At least 39/40 |
| Floor | Telegram card | 25/25 · 100.0% | 25/25 |
| Warmmiete | Telegram card | 20/20 · 100.0% | 20/20 |

### Cost assumptions

The final 600-check run cost `$1.412906`, or `$0.00235` per attempted check.

At a planning volume of 15,000 checks per year, the measured cost pattern would
be about `$35` per year (`$2.94` per month). A 25% planning buffer produces
`$0.00294` per check, about `$45` per year (`$3.68` per month).

The 15,000-check figure is a planning scenario, not a forecast. Berlin reported
12,398 apartment re-lettings by six state-owned housing companies in 2024,
excluding Berlinovo.

The estimate covers AI API calls only. It excludes source access, hosting,
monitoring, duplicate listings, price changes, differences in real-listing
length and human review. It uses prices recorded on 30 July 2026.

Evidence:

- [Evaluation plan](eval/AI_QA_EVAL_PLAN.md)
- [Final 600-listing report](eval/runs/extraction-v1-final-600/report.md)
- [Repository](https://github.com/mich-mayer/flatfeed)
- [Berlin volume reference](https://www.berlin.de/sen/stadt/presse/pressemeldungen/pressemitteilung.1628093.php)

## 5. Next

### What should FlatFeed test with permitted sources?

- **Source access and format:** Can FlatFeed secure a permitted data channel
  from each relevant provider and confirm what format the data comes in?
- **Fast delivery:** How quickly do new listings reach FlatFeed after providers
  publish them?
- **User value:** Are alerted listings still available and worth pursuing for
  users?
- **Conditional review loop:** If a source requires text extraction, can admin
  review help fix parser errors and improve the AI check when an alert is wrong?

## What this demonstrates

### A working apartment-search workflow, with rules making the match.

I built and tested the saved-filter Telegram flow and evaluated one plausible
way to process text-based listings with bounded AI QA. Matching remains
rule-based; how listings enter FlatFeed in production should depend on the
access terms, formats and data quality providers actually offer.

## Another case

Opsqora uses AI differently: AI groups support feedback while people decide
what to build.

[Read the case study →](https://mich-mayer.github.io/opsqora/case-study.html)
