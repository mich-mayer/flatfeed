# FlatFeed

FlatFeed is a Telegram bot and Streamlit dashboard prototype for collecting
Berlin WBS apartment listings from source adapters and matching them to user
filters. The current demo uses synthetic listings instead of scraping real
housing companies, then demonstrates deterministic parsing, matching, AI QA,
and evals in a defensible portfolio setting.

## What It Shows

- Synthetic Berlin apartment catalog with hidden ground truth.
- Source-adapter architecture for collecting listings from multiple catalogs.
- Fixed Telegram filter setup: WBS, Bezirk, max Kaltmiete, and room count.
- Deterministic parsing for WBS, prices, rooms, floor, address, and district.
- Deterministic matching and one-time Telegram notifications.
- Local S-Bahn/U-Bahn walking-time estimates from bundled station coordinates.
- Optional admin-only AI QA for parser review; AI never mutates listings.
- Eval runner that compares parser output with synthetic golden truth.
- Streamlit "product operations" dashboard: pipeline readiness, source trust,
  live parsing accuracy, AI QA usefulness/cost, and proven/unproven evidence.

No real source scraping, image reuploading, Google Maps, Photon geocoding, or
server deployment scripts are part of the current demo product. The collection
layer is represented by the synthetic source adapter and shared ingestion
pipeline.

## Working on This Repo

Durable project context lives in the repository so humans, Claude, and Codex use
the same source of truth:

- `CLAUDE.md`: entry context for Claude and Claude Code.
- `AGENTS.md`: entry context for Codex and other coding agents.
- `DESIGN_CONTENT_SYSTEM.md`: the normative design, content, terminology,
  accessibility, and case-study standard.
- `docs/PROJECT_CONTEXT.md`: product semantics — filters, listing card, parsing
  rules, AI QA boundaries, data model, and reliability decisions.
- `docs/agent-workflow.md`: the single rulebook for humans and AI agents —
  required response context, guardrails, Phase 1 boundaries, build/verify,
  working style, and collaboration rules.

`CLAUDE.md` and `AGENTS.md` are thin pointers; the working rules are not
duplicated across them.

## Project Structure

```text
.
├── data/
│   └── berlin_transit_stations.csv
├── eval/
│   └── run_eval.py
├── scripts/
│   ├── init_db.py
│   └── ingest_synthetic.py
├── synthetic/
│   ├── case_catalog.py
│   ├── generator.py
│   └── golden_set.py
├── flatfeed/
│   ├── ai_qa.py
│   ├── config.py
│   ├── listing_metadata.py
│   ├── matching.py
│   ├── parser.py
│   ├── wbs_rules.py
│   ├── dashboard/
│   │   └── streamlit_app.py
│   ├── db/
│   ├── ingestion/
│   │   └── synthetic.py
│   └── nlp/
├── main.py
└── requirements.txt
```

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env.local
```

Set at least:

```env
TELEGRAM_BOT_TOKEN=123456:your-test-bot-token
ADMIN_TELEGRAM_USER_IDS=123456789
BOT_BACKGROUND_ENABLED=false
AI_QA_PROVIDER=mock
```

Initialize the database:

```bash
ENV_FILE=.env.local python scripts/init_db.py
ENV_FILE=.env.local python scripts/ingest_synthetic.py
```

Run the bot:

```bash
ENV_FILE=.env.local python main.py
```

Run the dashboard:

```bash
ENV_FILE=.env.local streamlit run flatfeed/dashboard/streamlit_app.py
```

## Demo Script

New visitors (hiring managers, first-time testers) get a 5-screen,
product-first guided tour instead of the raw filter wizard:

1. Send `/start`, or open `https://t.me/FlatFeedBot?start=tour` directly.
   Both lead to the same intro with `Start the tour` / `Skip the tour`.
2. **Step 1 — One renter job:** shows a realistic filter as plain text.
   Held ephemeral — nothing is saved yet.
3. **Step 2 — The result:** runs the real matching predicate and the real
   source-activity check over the live catalog, then shows the resulting
   listing card as "1 of N active matches" plus why it matched.
4. **Step 3 — Rules make the decision:** the product pipeline (Collect →
   Normalize → Verify → Match → Deliver) and the privacy facts. No AI here.
5. **Step 4 — AI checks a narrow risk:** the one AI step. Injects a live WBS
   fault and shows the resulting AI QA alert with the same triage buttons a
   real admin sees, attached to the same message.
6. **Step 5 — What this prototype proves:** `Working now` / `Measured on
   synthetic data` (a live golden-set count) / `Not yet proven`, plus
   `Use this demo filter` (saves it only now, on request), `Set up my own
   filter`, and `Read the case study`.
7. Nothing tapped during the tour is written to `ai_qa_reviews` or `users`
   before that explicit final choice — the fault injection and triage are
   display-only, so ten visitors never skew the metrics or each other's
   filters. See `docs/PROJECT_CONTEXT.md` for the full guarantee.
8. `🛠 Admin` is visible to every visitor as a demo view (including
   `Replay the tour`); actions that change catalog data or spend budget stay
   restricted to `ADMIN_TELEGRAM_USER_IDS` and say so if tapped without
   admin rights.
9. As an admin, `🛠 Admin` -> `Run QA demo` runs the same ephemeral
   fault-injection flow over a few catalog listings; `Review flagged issues`
   and `Run catalog QA` are the real, persisting admin paths.
10. Tap `📊 Effectiveness dashboard` in the admin panel (or open the
    dashboard directly) to inspect the product-operations view: pipeline
    readiness, source trust, live parsing accuracy, AI QA usefulness/cost,
    and proven/unproven evidence.

The persistent chat keyboard keeps the main story visible:

```text
🔎 Show matches
⚙ Filter    📂 All listings
🛠 Admin
```

The Telegram command menu publishes `/start`, `/filter`, `/matches`, `/help`,
and `/delete`. `/delete` (data removal) is also available as a `🗑 Delete my
data` button on the filter card, keeping the privacy action discoverable.

## Eval

Run deterministic parser eval on the synthetic golden set:

```bash
ENV_FILE=.env.local python -m eval.run_eval
```

JSON output:

```bash
ENV_FILE=.env.local python -m eval.run_eval --json
```

Use `--provider openai` only for optional AI QA experiments with an API key and
explicit budget settings. The default OpenAI QA model is `gpt-5.4-mini`, with
pricing configured as `$0.75 / 1M` input tokens and `$4.50 / 1M` output tokens.

Eval result numbers are quoted by hand in `CASE_STUDY.md` and
`docs/case-study.html`. After any eval run that changes them, check every
quoted occurrence stayed in sync:

```bash
PYTHONPYCACHEPREFIX=/tmp/flatfeed-pycache .venv/bin/python -m scripts.check_eval_numbers
```

## Environment Variables

See `.env.example` for the full list. The main product-specific settings are:

```env
DATABASE_URL=sqlite:///./data/flatfeed.db
AI_QA_PROVIDER=mock
BOT_BACKGROUND_ENABLED=false
DASHBOARD_URL=
SYNTHETIC_SEED=20260623
SYNTHETIC_LISTING_COUNT=15
MANUAL_REFRESH_TIMEOUT_SECONDS=120
SOURCE_FAILURE_ALERT_THRESHOLD=3
SOURCE_ALERT_COOLDOWN_SECONDS=3600
```

OpenAI is optional:

```env
OPENAI_API_KEY=
AI_QA_ENABLED=false
AI_QA_PROVIDER=mock
AI_QA_MODEL=gpt-5.4-mini
OPENAI_INPUT_PRICE_PER_1M=0.75
OPENAI_OUTPUT_PRICE_PER_1M=4.50
```

## Development Checks

```bash
PYTHONPYCACHEPREFIX=/tmp/flatfeed-pycache .venv/bin/python -m unittest discover -s tests
PYTHONPYCACHEPREFIX=/tmp/flatfeed-pycache .venv/bin/python -m eval.run_eval
PYTHONPYCACHEPREFIX=/tmp/flatfeed-pycache .venv/bin/python -m scripts.check_eval_numbers
git diff --check
```

## Notes

- WBS remains a legitimate domain term: do not remove WBS parsing, labels, or
  matching semantics.
- Synthetic case tags and ground truth must stay out of parser/AI QA prompts.
- AI QA findings are admin-only and require human feedback.
- User-facing listing cards are formatted in `flatfeed/matching.py`.
- Listing photos are third-party Wikimedia Commons demo assets with separate
  attribution and license details in `assets/listing_photos/LICENSES.md`.
- Synthetic listing URLs (the card's `Open listing` link) point at
  `docs/demo-listing.html`, a static GitHub Pages explainer — not a live
  housing site. See `docs/PROJECT_CONTEXT.md` for the activity-check
  mechanics.
