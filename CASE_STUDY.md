# FlatFeed Case Study

FlatFeed is my AI Product Management portfolio project for Berlin WBS apartment
listing collection and matching. I built it to show how I think about
AI-assisted product systems where reliability, explainability, privacy, and
measurable quality matter more than feature count.

## 1. The Problem

Finding WBS-eligible apartments in Berlin is fragmented and time-sensitive:
listings appear across different sources, use inconsistent formats, change
quickly, and often hide key eligibility details inside unstructured text. The
affected user is a renter who must repeatedly check multiple catalogs and
manually interpret WBS, district, rent, room count, and availability before they
can even decide whether an apartment is worth opening.

## 2. Why AI?

The core matching flow should not depend on AI because eligibility decisions
need to be predictable and explainable. I used deterministic parsing and rules
for user-facing matching, then used AI as a controlled QA layer to review parser
snapshots, flag ambiguous or risky fields, and help improve coverage over time.
AI is useful here because listing text contains edge cases, wording variation,
and ambiguity that are expensive to review manually at scale, but the product
still keeps AI away from automatic data mutation.

## 3. My Role

I defined the product scope, shaped the portfolio positioning, designed the
source-collection and matching flow, implemented the prototype, created the
synthetic evaluation dataset, wrote deterministic parsing rules, added AI QA
with budget controls, and built the admin dashboard for review and measurement.
I treated the project as an end-to-end AI PM case: problem framing, trade-off
definition, prototype delivery, evaluation, and honest documentation.

## 4. The Approach

I scoped the product around a trusted catalog rather than a generic real-estate
search tool. The data strategy uses synthetic Berlin listings with hidden
ground truth so the parser can be evaluated without scraping or redistributing
real housing-company listings. I chose deterministic parsing for fields that
directly affect matching, a source-adapter ingestion layer for future multi-
source collection, SQLite for a local prototype, and AI QA only as an
admin-reviewed control layer. The main trade-off was deliberately limiting live
source coverage in order to make the demo privacy-safe, defensible, and
measurable.

## 5. What I Built

I built a Telegram bot and Streamlit dashboard prototype. The bot stores a
fixed user filter for WBS, Berlin district, maximum Kaltmiete, and rooms, then
returns active listings that match. The ingestion layer normalizes source
listings into a shared schema, enriches local transit walking-time estimates,
tracks source activity, deduplicates sent notifications, and records source
health. The AI QA system reviews parser snapshots, logs cost and token usage,
flags high-risk issues for an admin, and keeps human feedback separate from
automatic matching.

## 6. Results

In the current synthetic golden-set eval, FlatFeed parses 15 synthetic listings
with 100.0% parser field accuracy and 100.0% exact listing accuracy across WBS,
rent, rooms, floor, district, postal code, and special constraints. The mock AI
QA provider produced 0 false alert fields and $0.000000 total QA cost in that
demo run. These are synthetic evaluation metrics, not production user-impact
numbers, but they demonstrate that the prototype has a measurable quality loop
instead of relying on anecdotal demos.

## 7. What I Learned

The biggest lesson is that AI PM work is strongest when the AI boundary is
clear. For this product, deterministic rules create trust for user-facing
matching, while AI adds value as a review and learning layer. If I continued
the project, I would add a small set of live source adapters where terms allow
it, expand the golden set, add screenshots from a real demo session, and compare
AI QA prompt versions over time with human-reviewed feedback.

