# Project Context

## Purpose

FlatFeed is a portfolio prototype for Berlin WBS apartment collection and
matching. It demonstrates how a bot can collect listings through source
adapters, normalize them into one trusted catalog, and match them to user
filters. The prototype emphasizes reliable parsing, deterministic matching,
AI-assisted QA, cost controls, and measurable evaluation without scraping or
redistributing real housing-company listings.

The target portfolio role is AI Product Manager in a corporate environment.
Reliability, explainability, privacy, defensibility, measurable AI quality, and
cost control matter more than feature count.

## Current Product

### Source collection

- `FlatFeed Synthetic`: generated local listings from `synthetic/`.
- No real housing-company source adapters are enabled or present.
- Synthetic listing URLs use `https://demo.flatfeed.local/listings/<id>` and
  are checked locally by the source adapter. No network request is made.
- The product positioning should still mention collection from different
  sources: the codebase has a source-adapter registry, ingestion history,
  per-source activity checks, and per-source health monitoring. In the demo,
  those capabilities are exercised through the synthetic adapter rather than
  live external catalogs.

### User filter

The fixed Telegram filter asks for:

1. WBS: any WBS, 100, 140, 160, 180, 220, or no WBS required.
2. Berlin Bezirk: one of the 12 Bezirke or any.
3. Maximum Kaltmiete: user-entered amount.
4. Rooms: 1, 2, 3, 4, 5+, or any.

The visible label is `District`. Internally and semantically it is a Bezirk.
Ortsteil/Kiez names in synthetic text are normalized to one of the 12 Berlin
Bezirke.

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

### Synthetic ingestion and notifications

```text
Synthetic catalog generation
  -> upsert listings and mark missing synthetic URLs inactive
  -> deterministic listing parsing at ingestion (no LLM)
  -> local transit enrichment from embedded coordinates
  -> optional AI QA for newly discovered listings
  -> match new listings against saved filters
  -> notify eligible users once
```

`BOT_BACKGROUND_ENABLED` defaults to `false` so local demo runs do not start
polling/scanning unless explicitly requested.

### User-requested listings

- Show matches: select newest candidates matching the saved filter, check
  activity through the synthetic adapter, and send at most 10 valid cards. This
  is the primary user-facing listing action.
- Browse demo catalog: load active candidates from SQLite, randomize, check
  activity through the synthetic adapter, and send at most 10 valid cards. This
  is a secondary demo action and ignores the saved filter.
- A failed activity check marks the local listing inactive and excludes it from
  delivery.

SQLite accelerates selection and preserves history. The synthetic catalog is the
demo source of truth.

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

Synthetic listing cards use a small local pool of illustrative photos of Berlin
multi-family residential buildings. The photos are assigned deterministically
from `assets/listing_photos/` and are not representations of the specific
synthetic listing address. Source, author, and license details are documented in
`assets/listing_photos/LICENSES.md`.

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
- Backfill covers active listings missing the current review version.
- Daily count and dollar budgets stop excessive usage.
- Risk at or above the configured threshold creates an admin-only alert.
- The admin labels the finding parser error, parser correct, or unsure.
- AI output never alters listing data, matching, or user-facing cards
  automatically.

The Streamlit dashboard is focused on AI QA coverage, reviewed scale, human
feedback quality, false positives/confirmed errors, field-level patterns,
prompt version comparison, and model cost.

## Data Model

Important tables:

- `users`: Telegram ID, saved filter, filter update timestamp.
- `listings`: parsed listing, raw text, activity, first/last seen state.
- `sent_listing_notifications`: notification deduplication.
- `ingestion_runs`: source health and alert history.
- `ai_qa_reviews`: versioned AI review, parser snapshot, usage/cost, feedback.
- `api_logs`: OpenAI token and cost logging.
- `source_companies`: currently seeded with `FlatFeed Synthetic`.

Schema evolution uses the idempotent compatibility logic in
`flatfeed/db/session.py`, not a full Alembic migration stack.

Users can remove their saved filter and notification dedupe history with
`/delete` or the `🗑 Delete my data` button on the filter card. Both ask for an
explicit confirmation before deleting.

## Reliability Decisions

- Empty synthetic results are suspicious and are recorded as ingestion failure.
- Three consecutive failures trigger an admin alert by default; cooldown avoids
  alert spam.
- Partial collection must not mass-mark unseen listings removed.
- Manual refresh and user listing actions have timeouts and user-facing failure
  messages.
- Removed listings remain in history but are excluded from active delivery.

## Known Constraints

- SQLite is appropriate for this local portfolio prototype.
- The codebase is English-facing. Keep future copy changes consistent across
  bot UI, dashboard UI, tests, and documentation.
