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

I defined the product scope, shaped the portfolio positioning, and designed the
source-collection and matching flow, the deterministic parsing rules, the
synthetic evaluation dataset, and the AI QA budget controls. Solo project: all
product decisions, scope boundaries, and rules are mine. Implementation — the
bot, the dashboard, and the eval harness — was built with AI coding agents
(Claude Code and Codex) under a documented collaboration workflow in the repo.
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

On the Build/Buy/Wrapper axis the split is deliberate: parsing and matching are
built in-house and run fully locally (no LLM, no tokens, zero inference cost)
because that logic must stay owned and explainable, while the QA layer is a thin
wrapper on a small hosted model, since reviewing listing text is a commodity
language task with no data moat. AI QA ships behind a mock provider by default, a
hard daily cost cap, and a risk threshold that only escalates risk-scored
findings above threshold, so it stays optional and bounded. Evaluation is
designed in from the start: a 15-listing synthetic golden set with hidden ground
truth, scored by a runnable harness for parser field accuracy and exact-listing
accuracy.

That scope is also a compliance posture, not just a demo convenience: the
synthetic catalog keeps real personal and housing data out of the prototype, and
because AI never decides a person's eligibility (matching is deterministic and AI
only reviews parser quality), the prototype is designed to avoid solely automated
eligibility decisions of the kind GDPR Art. 22 focuses on. A live rollout would
still need formal legal review, especially around housing access, AI Act risk
classification, provider terms, and user-facing transparency.

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

100% on a 15-listing synthetic golden set means the parser covers every case I
designed for it — not that parsing is solved. The harness exists so the number
can drop, visibly, when live sources land.

## 7. What I Learned

The biggest lesson is that AI PM work is strongest when the AI boundary is
clear. For this product, deterministic rules create trust for user-facing
matching, while AI adds value as a review and learning layer. What I would do
differently: run one real AI QA pass on a small hosted model earlier — the mock
provider made the loop safe to build, but a single real run would have priced
the prompt trade-offs sooner. If I continued the project, I would add a small
set of live source adapters where terms allow it, expand the golden set, add
screenshots from a real demo session, and compare AI QA prompt versions over
time with human-reviewed feedback.
