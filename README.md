# FlatFeed

FlatFeed is a working Telegram prototype for matching Berlin WBS apartment
listings against four renter criteria. The current version runs on one
synthetic source adapter: it demonstrates the end-to-end workflow and its
reliability controls, not live housing coverage or renter outcomes.

## What It Shows

- Four-field Telegram filter: WBS, district, max Kaltmiete, and rooms.
- Deterministic parsing and matching with fail-closed unknown values.
- Standardized listing cards and a synthetic-adapter state check.
- Optional background notification deduplication.
- 15 authored synthetic cases currently pass the parser regression check.
- Optional admin QA workflow; the public demo uses a deterministic mock and QA
  cannot mutate listings or matching rules.

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
- `docs/CURRENT_STATUS.md`: concise current handoff — experiment result,
  consumed evidence, current decision, and recommended next step.
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

## Guided Demo

Send `/start`, or open `https://t.me/FlatFeedBot?start=tour` directly. The core
tour has three steps:

1. A four-field demo filter is shown without saving it.
2. The same matching predicate as the main product path runs against the
   synthetic catalog and returns one standardized card with match reasons.
3. The bot separates what is implemented and regression-checked from what has
   not been validated with live sources or renters.

Only `Use this demo filter` writes the temporary filter to the user record. The
AI QA fault simulation remains available as an optional branch after the core
tour; it uses a deterministic mock and stores no tour feedback.

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

Public portfolio surfaces quote only the authored regression-case count. Field
accuracy and mock-provider diagnostics stay in the runnable eval report. After
an eval change, verify the public count remains synchronized:

```bash
PYTHONPYCACHEPREFIX=/tmp/flatfeed-pycache .venv/bin/python -m scripts.check_eval_numbers
```

A separate synthetic offline hosted-model feasibility experiment is documented
in `eval/AI_QA_EVAL_PLAN.md`. `gpt-5.6-terra` with high reasoning passed one
frozen synthetic validation, then failed the one 600-case locked holdout
because rooms correct-field recall was 43/50, below the predeclared 45/50
minimum. The configuration is therefore not finally accepted. Live-source
performance remains unmeasured, and nothing was integrated into the product
runtime.

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
  attribution and license details in `assets/listing_photos/LICENSES.md`. The
  guided-tour showcase uses an address-aligned Schlangenbader Straße 91 photo; its
  apartment details remain synthetic.
- Synthetic listing URLs (the card's `Open listing` link) point at
  `docs/demo-listing.html`, a static GitHub Pages explainer — not a live
  housing site. See `docs/PROJECT_CONTEXT.md` for the activity-check
  mechanics.
