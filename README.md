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
- Streamlit dashboard for AI QA coverage, feedback, cost, and parser issues.

No real source scraping, image reuploading, Google Maps, Photon geocoding, or
server deployment scripts are part of the current demo product. The collection
layer is represented by the synthetic source adapter and shared ingestion
pipeline.

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

1. Send `/start`. The bot greets you and shows your (empty) filter card with a
   `Set up filter` button — it no longer forces the wizard on you.
2. Set the filter step by step: WBS, district, Kaltmiete, and rooms. Each step
   shows `Step N/4` and offers `⬅ Back` / `✖ Cancel`; the WBS and Kaltmiete
   steps include a short plain-language explainer.
3. Tap `🔎 Show matches` to receive active synthetic listings that match the
   saved filter.
4. As an admin, tap `🛠 Admin` -> `Run QA demo`.
5. Review the flagged parser report and triage it as `Parser error`,
   `Parser correct`, or `Borderline / unsure`.
6. Tap `📊 Effectiveness dashboard` in the admin panel (or open the dashboard
   directly) to inspect AI QA coverage, cost, feedback, and parser issue
   patterns.

The persistent chat keyboard keeps the main story visible:

```text
🔎 Show matches
⚙ Filter    📂 All listings
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
