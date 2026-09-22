# Product architecture and behavior

## Purpose

FlatFeed is a working Telegram portfolio prototype for reducing repeated checks
across Berlin WBS listings. A user saves four criteria, requests matches from a
synthetic catalog and reviews each match in one consistent listing card. The prototype emphasizes reliable parsing,
deterministic matching, and measurable offline AI evaluation without scraping
or redistributing real housing-company listings. It is an interactive product
prototype, not a usable live housing feed. The public case study uses captures
from that implemented flow; model-evaluation evidence lives in the case study
and `eval/` artifacts.

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
- The codebase has a source-adapter registry, ingestion history, per-source
  activity checks and source-health monitoring. The prototype exercises these
  capabilities through the synthetic adapter rather than live external catalogs.

### Saved filter

The public bot lets a user save:

1. WBS: any WBS, 100, 140, 160, 180, 220, or no WBS required.
2. Berlin Bezirk: one of the 12 Bezirke or any.
3. Maximum Kaltmiete: user-entered amount.
4. Rooms: 1, 2, 3, 4, 5+, or any.

The visible label is `District`. Internally and semantically it is a Bezirk.
Ortsteil/Kiez names in synthetic text are normalized to one of the 12 Berlin
Bezirke. The filter is stored against the Telegram user ID until reset or
deleted.

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

The bot and documentation are English-facing. WBS stands for
Wohnberechtigungsschein, a certificate used to qualify for subsidized housing
in Berlin.

## Main Flows

### Saved-filter pipeline

```text
Synthetic catalog generation
  -> upsert listings and mark missing synthetic URLs inactive
  -> deterministic listing parsing at ingestion (no LLM)
  -> local transit enrichment from embedded coordinates
  -> optional AI QA for newly discovered listings
  -> compare listings with the saved user criteria
  -> show up to three verified matches on demand
  -> optionally send each newly collected match once
```

Users can request matches on demand. When `BOT_BACKGROUND_ENABLED=true`, the
runtime also starts the implemented collection loop and sends each newly
collected match once; the default demo setup keeps this switch off.

SQLite accelerates selection and preserves history. The synthetic catalog is the
prototype source of truth.

### Telegram product flow

`/start` opens the filter home and the persistent `Show matches` / `Filter`
menu:

1. **Filter setup** — a four-step button flow saves WBS type, district,
   maximum Kaltmiete and rooms to `users`.
2. **On-demand matching** — `is_listing_match` compares the active synthetic
   catalog with the saved filter, then `_verified_active_matches` applies the
   synthetic adapter's local activity check.
3. **Results** — the bot sends the canonical `format_match_message` card for
   each of up to three on-demand results, without a separate explanation message.
4. **Filter management** — the user can edit individual fields, reset the
   filter or delete all saved FlatFeed data.

The entry message discloses once that the catalog is synthetic. `/help` explains
the optional notification mode, and the card identifies `FlatFeed Synthetic`
as its source.

Rules that keep the product flow safe and honest:

- **Explicit personal state.** Only the button-based setup writes the saved
  filter. `/delete` removes the user record and notification history after a
  consequence-named confirmation.
- **Synthetic disclosure.** The entry names the synthetic catalog, and each
  result card names `FlatFeed Synthetic` as its source.
- **AI boundary.** The user-facing path is deterministic. The optional
  admin-only AI parser check cannot change listing fields, matching decisions
  or user-facing cards.
- **Honest empty state.** An arbitrary filter may have no result in the small
  catalog; the response states that this does not describe the live Berlin
  housing market.
- **Legacy compatibility.** Buttons from the retired guided tour redirect to
  the current filter home without writing filter state themselves.

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
synthetic listing address. The primary showcase is deliberately stricter:
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

Source attribution and the limits of the recorded snapshot provenance are in
[the transit dataset documentation](../data/README.md).

There is no Photon, Google Maps, or other network geocoding path. Listings
without coordinates are skipped for transit enrichment.

## AI QA

AI QA exists to measure and improve deterministic parser quality. Listing
parsing itself is fully deterministic and makes no LLM calls. There are two
separate QA contracts; evidence from one must not be attributed to the other.

### Optional runtime QA

`flatfeed/ai_qa.py` receives raw text and a parser snapshot. Its versioned
contract returns a model risk assessment, issues and advisory values; runtime
guardrails decide whether to alert a configured admin. It is disabled by default
and is not the checker measured by the final 600-case evaluation.

- Provider configured by `AI_QA_PROVIDER`.
- `mock` is local, deterministic, and free.
- `openai` is optional, admin-only, budgeted, and never required for matching.
- Runtime model, pricing and budget defaults are recorded in
  [configuration](../flatfeed/config.py). The prompt version is defined in
  [the runtime QA implementation](../flatfeed/ai_qa.py).
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

### Separate offline extraction evaluation

The [final protocol](../eval/AI_QA_EVAL_PLAN.md) describes `extraction-v1`, using
`gpt-5.6-terra` with high reasoning. The model receives only raw listing text and
returns exact source quotes. Deterministic code compares them with the parser
snapshot and produces `review_required`; the model never sees that snapshot.
On one fresh frozen 600-case synthetic evaluation the check found and localized
300/300 planted errors, raised 0/300 false alerts, and returned 599/600 usable
checks. All predeclared synthetic gates passed. This configuration is not
integrated into product runtime; its flags were evaluated offline rather than
delivered to an operational admin queue. Live-source accuracy is unmeasured.
The [evaluation guide](../eval/README.md) links the artifacts and prior history.

## Data Model

Important tables:

- `users`: Telegram ID and saved-filter records for the current product flow.
- `listings`: parsed listing, raw text, activity, first/last seen state.
- `sent_listing_notifications`: notification deduplication.
- `ingestion_runs`: source health and alert history.
- `ai_qa_reviews`: versioned AI review, parser snapshot, usage/cost, feedback.
- `api_logs`: OpenAI token and cost logging.
- `source_companies`: currently seeded with `FlatFeed Synthetic`.

Schema evolution uses the idempotent compatibility logic in
`flatfeed/db/session.py`, not a full Alembic migration stack.

`/delete` is a public command and filter-card action. It removes the saved
filter and notification-dedupe records after explicit confirmation.

## Reliability Decisions

- Empty synthetic results are suspicious and are recorded as ingestion failure.
- Three consecutive failures trigger an admin alert by default; cooldown avoids
  alert spam.
- Partial collection must not mass-mark unseen listings removed.
- User listing actions have bounded candidate counts and user-facing failure
  messages.
- Removed listings remain in history but are excluded from active delivery.

## Scope and evidence

This is a local SQLite-backed prototype over synthetic data. Implemented
mechanics do not establish live-source coverage, real-world parser accuracy or
renter outcomes. See [prototype status](STATUS.md) for the accepted evidence
and limitations, and [README](../README.md#development-checks) for local checks.
