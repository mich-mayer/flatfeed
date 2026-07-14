# FlatFeed Case Study

FlatFeed is a functional Telegram prototype for matching Berlin WBS apartment
listings against four renter criteria: WBS tier, district, maximum Kaltmiete,
and room count. The current version runs on a synthetic catalog. It demonstrates
the product workflow and its reliability controls; it does not demonstrate live
source coverage or renter outcomes.

WBS (Wohnberechtigungsschein) is a certificate used to qualify for subsidized
housing in Berlin. Kaltmiete is rent before utilities.

## 1. Product Hypothesis

The premise is that WBS renters repeatedly inspect fragmented listing formats
and apply the same basic checks. FlatFeed tests a narrower job: save one filter,
then inspect matching listings in a consistent Telegram card.

This premise has not yet been validated through renter research. The prototype
exists to make that next test concrete, not to imply a launched housing service.

## 2. Product and Role

The main path is:

```text
Filter → Normalize → Check → Match → Notify
```

- A renter sets four filter fields.
- Fixed parsing rules normalize listing text.
- The current synthetic adapter checks the listing's state in its local catalog.
- Deterministic rules compare all four fields and explain a match.
- An optional background path deduplicates newly seen matches against stored
  delivery history.

I owned the problem framing, scope, interaction rules, reliability trade-offs,
and evaluation design. I implemented the bot, dashboard, and test harness with
Claude Code and Codex as coding collaborators.

## 3. Key Decisions

### Four fields, not a generic search

The prototype keeps only the fields used in its match decision. Unknown rent or
room values fail closed instead of producing a confident-looking match. This is
a four-criteria match, not a complete assessment of every housing restriction.

### Rules decide what renters see

Parsing and matching are deterministic. The repository also contains an
optional admin QA workflow that can flag parser mismatches. The public demo uses
a deterministic mock provider; hosted-model usefulness has not been tested. QA
findings cannot automatically change listings, rules, or renter-facing results.

### Reliability before source count

The prototype implements a synthetic-adapter state check, optional background
notification deduplication, and deletion of the saved filter and delivery
history from the FlatFeed database. Only one synthetic source adapter is
implemented; there is no live housing-company ingestion in this version.

## 4. Evidence and Limits

Demonstrated now:

- temporary and saved four-field filter flows;
- deterministic matching and standardized Telegram cards;
- synthetic-adapter state checks and optional background deduplication;
- 15 synthetic test cases pass the regression check; live-source accuracy is
  not measured.

Not demonstrated yet:

- demand from real WBS renters;
- permitted live-source coverage and freshness;
- time saved or application outcomes;
- hosted-model QA usefulness, false-alarm rate, or real cost.

## 5. Next Test

Next, I would test the filter-to-listing flow with one permitted live source and
a small group of WBS renters. The decision would be based on filter completion,
useful listing opens, stale-card rate, and whether renters understand why a
listing matched.
