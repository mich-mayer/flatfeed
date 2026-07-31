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
- Synthetic listing URLs point at the static explainer page
  `docs/demo-listing.html` (published on GitHub Pages as
  `https://mich-mayer.github.io/flatfeed/demo-listing.html?id=<id>`) so the
  card's `Open listing` link resolves to something real for an external
  viewer. Activity is still checked locally by the source adapter via a
  string-prefix match on the URL; no network request is made for the check
  itself, and the demo page is a static, honest disclosure, not a per-listing
  detail page.
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
  -> optional background notification with delivery-history deduplication
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

### Guided tour

`/start` (plain or via the `https://t.me/FlatFeedBot?start=tour` deep link)
leads every visitor into a 3-step, button-only tour before the regular
filter/matches flow:

1. **One renter job** — shows the demo filter as plain text (WBS type, district,
   Kaltmiete, rooms). Held ephemeral: nothing is written to `users` yet.
2. **One match from the demo catalog** — runs the same matching predicate as the main
   product path (`is_listing_match`) over the synthetic catalog, then the
   synthetic adapter's local activity check (`_verified_active_matches`). It
   shows one standardized card plus field-level match reasons, and offers an
   optional `How matching works` pipeline explainer as a side branch.
3. **Evidence and limits** — separates implemented behavior and the live
   golden-set count from unvalidated renter demand, live-source coverage, and
   AI QA performance on live-source listings. `Use this demo filter` saves the
   filter only now, on explicit request.

The parser-fault and triage simulation is an optional branch after step 3. It
is not part of the renter flow and the public demo uses a deterministic mock
provider, not a hosted model.

The tour listing is selected deterministically from the active catalog (2
rooms, a WBS requirement including 140, a WBS phrase in the raw text, and
transit data) — see `_select_tour_listing` in `main.py`. `Skip the tour` and
`🛠 Admin` -> `Replay the tour` are always available.

Rules that keep the tour safe and honest to run in front of any visitor:

- **Ephemeral filter.** The demo filter is derived from the tour listing on
  every screen and is never persisted until the visitor explicitly taps
  `Use this demo filter` on step 3 (`tour:save_filter` ->
  `save_fixed_preferences`).
- **Ephemeral fault injection and triage.** The tour's fault injection
  (`_send_tour_inject`) and its triage responses (`_send_tour_feedback_response`)
  never add or commit an `AIQAReview` row. They reuse the real admin alert
  formatter (`_format_ai_qa_review`, with `include_cost=False` and
  `include_confidence=False` for the tour) and the real triage keyboard, so
  a visitor sees the same message format and buttons a real admin alert
  uses, without ever writing to the table the dashboard reads from. Every
  triage label gets the same neutral response — the tour states the fact
  (what the text says) without grading the visitor's choice. The dashboard's
  AI QA queries only count reviews whose `qa_prompt_version` exactly equals
  `CURRENT_AI_QA_PROMPT_VERSION` and additionally exclude any
  `-demo`-suffixed version as defense in depth, even though nothing writes
  rows shaped that way.
- **Demo admin view.** `🛠 Admin` is visible to every visitor
  (`main_menu_keyboard` no longer gates it), with a caption stating this is a
  demo view for non-admins. Every individual admin action inside keeps its
  existing `_is_admin_user` gate unchanged — a non-admin tapping `Run QA
  demo`, `Refresh catalog`, `Run catalog QA`, `Review flagged issues` (which
  writes real feedback), `View QA metrics`, or the dashboard auto-start
  button gets the existing "only available to admins" response. Only opening
  the panel itself and `Replay the tour` are open to everyone — the tour's
  own step 4 is the actual open-to-all ephemeral demo entry point, not the
  admin panel's `Run QA demo` button.

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
- Backfill covers active listings missing the current review version.
- Daily count and dollar budgets stop excessive usage.
- Risk at or above the configured threshold creates an admin-only alert.
- The admin labels the finding parser error, parser correct, or unsure.
- AI output never alters listing data, matching, or user-facing cards
  automatically.
- A separate synthetic offline hosted-model feasibility experiment is recorded
  in `eval/AI_QA_EVAL_PLAN.md`. The final `extraction-v1` configuration used
  `gpt-5.6-terra` with high reasoning to extract exact source quotes, followed
  by deterministic comparison with the parser snapshot. On one fresh frozen
  600-case synthetic evaluation it found and localized 300/300 planted errors,
  raised 0/300 false alerts, and returned 599/600 valid checks. All
  predeclared synthetic gates passed. Live-source accuracy remains unmeasured
  and the experiment was not integrated into product runtime.

The Streamlit dashboard ("FlatFeed product operations") leads with the
product pipeline and deterministic-parsing accuracy — AI QA is one section
among five, not the whole page. See `DESIGN_CONTENT_SYSTEM.md` §8 for the
exact section order and rules (live `eval.run_eval` numbers, the `-demo`
exclusion, the small-number `fmt_share` rule, and the mock-confidence
label).

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
