# Project Context

## Purpose

FlatFeed is a guided portfolio prototype for reducing repeated checks across
Berlin WBS listings. One synthetic scenario demonstrates how a bot can collect
listings through a source adapter, normalize them into one catalog, and compare
them with four user criteria. The prototype emphasizes reliable parsing,
deterministic matching, and measurable offline AI evaluation without scraping
or redistributing real housing-company listings. The Telegram runtime is an
interactive demonstration, not a usable housing feed; model-evaluation evidence
lives in the case study and `eval/` artifacts.

The target portfolio role is AI Product Manager in a corporate environment.
Reliability, explainability, privacy, defensibility, measurable AI quality, and
cost control matter more than feature count.

## Current Product

### Source collection

- `FlatFeed Synthetic`: generated local listings from `synthetic/`.
- No real housing-company source adapters are enabled or present.
- Synthetic listing URLs point at the static disclosure page
  `docs/demo-listing.html` (published on GitHub Pages as
  `https://mich-mayer.github.io/flatfeed/demo-listing.html?id=<id>`) so the
  card's `Open listing` link resolves to something real for an external
  viewer. Activity is still checked locally by the source adapter via a
  string-prefix match on the URL; no network request is made for the check
  itself. The page makes clear that it is not a real offer or application flow.
- The product positioning should still mention collection from different
  sources: the codebase has a source-adapter registry, ingestion history,
  per-source activity checks, and per-source health monitoring. In the demo,
  those capabilities are exercised through the synthetic adapter rather than
  live external catalogs.

### Guided demo scenario

The public bot shows one temporary example containing:

1. WBS: any WBS, 100, 140, 160, 180, 220, or no WBS required.
2. Berlin Bezirk: one of the 12 Bezirke or any.
3. Maximum Kaltmiete: user-entered amount.
4. Rooms: 1, 2, 3, 4, 5+, or any.

The demo does not ask visitors to create or save a personal filter. The visible
label is `District`. Internally and semantically it is a Bezirk. Ortsteil/Kiez
names in synthetic text are normalized to one of the 12 Berlin Bezirke.

### Listing card

The Telegram card contains:

```text
District: <Bezirk>
Address: <street and house number, postal code Berlin>
Floor: <floor>
Rooms: <rooms>
S-Bahn: <minutes or not calculated>
U-Bahn: <minutes or not calculated>
WBS: <allowed WBS values / generic requirement / not required>
Source: <source>

Kalt: <price>
Warm: <price>

Open listing
```

The bot and documentation are English-facing. WBS remains a domain term for
Wohnberechtigungsschein and should not be translated away.

## Main Flows

### Synthetic demo pipeline

```text
Synthetic catalog generation
  -> upsert listings and mark missing synthetic URLs inactive
  -> deterministic listing parsing at ingestion (no LLM)
  -> local transit enrichment from embedded coordinates
  -> optional AI QA for newly discovered listings
  -> compare listings with the temporary demo criteria
  -> show one verified synthetic match in Telegram
```

The public runtime never starts background collection or user notifications.
Legacy storage and notification helpers remain in the repository for migration
compatibility, but they are not reachable from the current demo. The prototype
does not monitor live housing sources or send notifications about real new
listings.

SQLite accelerates selection and preserves history. The synthetic catalog is the
demo source of truth.

### Guided tour

`/start` (plain or via the `https://t.me/FlatFeedBot?start=tour` deep link)
leads every visitor into a 2-step, button-only demo:

1. **Example filter** — shows the demo criteria as plain text (WBS type,
   district, Kaltmiete, rooms). Nothing is written to `users`.
2. **Matching result** — runs the same matching predicate as the main
   product path (`is_listing_match`) over the synthetic catalog, then the
   synthetic adapter's local activity check (`_verified_active_matches`). It
   sends a short explanation with field-level reasons, then one canonical card using the same `format_match_message`
   card formatter. A separate follow-up message offers replaying the demo,
   opening the optional `How reliability works` explanation, or reading the case
   study. The walkthrough explicitly says that its example is synthetic and
   that the prototype does not monitor live housing sources or send
   notifications about real new listings.

The tour listing is selected deterministically from the active catalog (2
rooms, a WBS requirement including 140, a WBS phrase in the raw text, and
transit data) — see `_select_tour_listing` in `main.py`. `/start` restarts the
demo at any time.

Rules that keep the tour safe and honest to run in front of any visitor:

- **No personal state.** The demo criteria are derived from the tour listing on
  every screen and are never persisted. A compatibility handler rejects the
  retired `tour:save_filter` callback from older Telegram messages.
- **Synthetic disclosure.** The intro names the synthetic catalog before the
  first action, and the result card names `FlatFeed Synthetic` as its source.
- **AI boundary.** The user-facing path is deterministic. The optional
  reliability explanation names the separately evaluated, admin-only AI parser
  check; it cannot change listing fields, matching decisions or user-facing cards.
- **Guaranteed scenario.** The authored demo selects a compatible active
  synthetic listing so the visitor sees one complete matching result. It does
  not imply coverage of other filters or the live Berlin market.

## Parsing Semantics

### WBS

Supported user-facing percentages are 100, 140, 160, 180, and 220.

Examples:

- `WBS 100-140` -> `100, 140`
- `bis WBS 140` -> `100, 140`
- `WBS 140-220` -> `140, 160, 180, 220`
- `WBS 141-220` -> `160, 180, 220`; WBS 140 is excluded
- `WBS ab 160` -> `160, 180, 220`
- generic `WBS erforderlich` without a number -> `WBS required, type unknown`
- no WBS mention -> `No WBS required` by the current product convention
- explicit `ohne WBS`, `freifinanziert`, etc. -> `No WBS required`

The canonical implementation is `flatfeed/wbs_rules.py`. AI QA may challenge
the parser but cannot replace or mutate these rules automatically.

### Prices

- User matching is based only on Kaltmiete.
- A listing with unknown Kaltmiete does not match a user-entered maximum.
- Cards show both Kalt and Warm when available.
- Preserve cents in display and compare Kaltmiete using cents.

### Rooms and floor

- Rooms are exact except filter value `5`, which means 5 or more.
- A listing with an unknown room count does not match a room-specific filter.
- Household size phrases such as `3-Personenhaushalt` are not room counts.
- Floor extraction must not confuse `Etagenzahl` with the apartment floor.

### Address and district

- Prefer explicit address blocks over fallback prose regexes.
- Store the street/house number as address.
- Store the five-digit Berlin postal code separately and include it in cards.
- Normalize Ortsteil/Kiez names to one of the 12 Berlin Bezirke for `district`.
- AI QA reports include address source and sanity diagnostics.

## Synthetic Data And Eval

Synthetic cases live in `synthetic/case_catalog.py`. Each case has visible
listing text plus hidden truth fields for WBS, prices, rooms, floor, district,
coordinates, and special constraints.

Synthetic listing cards use a small local pool of photos of Berlin multi-family
residential buildings. Most are illustrative and are not representations of the
synthetic listing address. The guided-tour showcase is deliberately stricter:
its Schlangenbader Straße 91 photo, address, district, and coordinates refer to the
same real location. Apartment availability, rent, floor, rooms, and WBS eligibility
remain synthetic. Source, author, license, and modification details are
documented in `assets/listing_photos/LICENSES.md`; the case-study caption credits
the showcase photo at the point of display.

Golden data is loaded through `synthetic/golden_set.py`. The eval runner in
`eval/run_eval.py` compares parser output against the hidden truth and can
optionally run AI QA on the same cases.

Ground-truth fields and case tags must never be placed in listing text or URLs
sent to the parser or AI QA. They are eval-only metadata.

## Transit

Walking-time estimates use synthetic coordinates. The local VBB-derived station
CSV in `data/berlin_transit_stations.csv` is used to find the nearest S-Bahn and
U-Bahn geometrically. The algorithm multiplies straight-line distance by `1.25`
and assumes 80 meters per minute.

There is no Photon, Google Maps, or other network geocoding path. Listings
without coordinates are skipped for transit enrichment.

## AI QA

AI QA exists to measure and improve deterministic parser quality. It is the only
AI surface in the project: listing parsing itself is fully deterministic and
makes no LLM calls.

- Provider configured by `AI_QA_PROVIDER`.
- `mock` is local, deterministic, and free.
- `openai` is optional, admin-only, budgeted, and never required for matching.
- The default OpenAI QA model is `gpt-5.4-mini`; configured pricing is
  `$0.75 / 1M` input tokens and `$4.50 / 1M` output tokens.
- Current prompt version is defined in `flatfeed/ai_qa.py`; inspect the
  constant rather than trusting this document for the latest version.
- Each listing receives at most one review per prompt version.
- New listings are eligible for AI QA when enabled.
- Daily count and dollar budgets stop excessive usage.
- Risk at or above the configured threshold creates an admin-only alert.
- The admin labels the finding parser error, parser correct, or unsure.
- The public bot has no admin panel, dashboard, QA demo, backfill control, or
  model metrics. Configured admins can only receive and triage direct runtime
  alerts when optional runtime QA is explicitly enabled.
- AI output never alters listing data, matching, or user-facing cards
  automatically.
- A separate synthetic offline hosted-model feasibility experiment is recorded
  in `eval/AI_QA_EVAL_PLAN.md`. The final `extraction-v1` configuration used
  `gpt-5.6-terra` with high reasoning to extract exact source quotes, followed
  by deterministic comparison with the parser snapshot. On one fresh frozen
  600-case synthetic evaluation it found and localized 300/300 planted errors,
  raised 0/300 false alerts, and returned 599/600 valid checks. All
  predeclared synthetic gates passed. Live-source accuracy remains unmeasured
  and the experiment was not integrated into product runtime. Its public
  evidence lives in `docs/case-study.html` and `CASE_STUDY.md`.

## Data Model

Important tables:

- `users`: legacy Telegram ID and saved-filter records from earlier versions;
  the current demo does not create or update them.
- `listings`: parsed listing, raw text, activity, first/last seen state.
- `sent_listing_notifications`: notification deduplication.
- `ingestion_runs`: source health and alert history.
- `ai_qa_reviews`: versioned AI review, parser snapshot, usage/cost, feedback.
- `api_logs`: OpenAI token and cost logging.
- `source_companies`: currently seeded with `FlatFeed Synthetic`.

Schema evolution uses the idempotent compatibility logic in
`flatfeed/db/session.py`, not a full Alembic migration stack.

`/delete` remains as an unadvertised compatibility command so returning users
can remove saved-filter and notification-dedupe records created by an earlier
version. The current demo stores no personal filter or delivery history.

## Reliability Decisions

- Empty synthetic results are suspicious and are recorded as ingestion failure.
- Three consecutive failures trigger an admin alert by default; cooldown avoids
  alert spam.
- Partial collection must not mass-mark unseen listings removed.
- User listing actions have bounded candidate counts and user-facing failure
  messages.
- Removed listings remain in history but are excluded from active delivery.

## Known Constraints

- SQLite is appropriate for this local portfolio prototype.
- The codebase is English-facing. Keep future copy changes consistent across
  bot UI, tests, case-study surfaces, and documentation.
