# FlatFeed

FlatFeed is a working Telegram prototype for reducing repeated checks across
Berlin WBS listings. A user saves one four-field filter, requests matching
listings in a consistent format and can receive each new match once when
background delivery is enabled.
The prototype runs on a synthetic catalog; it does not provide live housing
coverage or measured user outcomes.

## What It Shows

- Saved four-field filter: WBS type, district, max Kaltmiete, and rooms.
- Deterministic parsing and matching with fail-closed unknown values.
- Consistent Telegram listing summaries with estimated walks to the nearest
  S- and U-Bahn stations.
- On-demand matching plus deduplicated notifications for newly collected matches.
- Filter editing, reset, and saved-data deletion in Telegram.
- Separately evaluated, admin-only AI parser-quality checks that cannot alter
  user-facing results.
- 15 authored synthetic cases currently pass the parser regression check.

No real source scraping, image reuploading, Google Maps, Photon geocoding, or
server deployment scripts are part of the current prototype. The collection
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

## Telegram Prototype

The public product surface is the working Telegram prototype. `/start` opens
the filter home and a persistent menu with `Show matches` and `Filter`.

The user can:

1. Set and save WBS type, district, maximum Kaltmiete, and rooms.
2. Request up to three active matches from the synthetic catalog.
3. Receive each new matching listing once when background delivery is enabled.
4. Review each result in the canonical listing-card format.
5. Edit or reset the filter and delete saved FlatFeed data.

The prototype states once at entry and in `/help` that its catalog is synthetic.
Set `BOT_BACKGROUND_ENABLED=true` to run the existing collection loop and send
new matching listings automatically; the default demo setup keeps it off.
`Open listing` resolves to a synthetic disclosure page, never a housing-company
page or application flow.

The Telegram command menu publishes `/start`, `/filter`, `/matches`, `/help`,
and `/delete`. Buttons from the retired guided walkthrough redirect to the
current saved-filter product flow without writing new state themselves.

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

The README records the authored regression-case count as a development check;
the public HTML and Markdown case studies do not present it as product evidence.
Field accuracy and mock-provider diagnostics stay in the runnable eval report.
After an eval change, verify the technical count remains synchronized:

```bash
PYTHONPYCACHEPREFIX=/tmp/flatfeed-pycache .venv/bin/python -m scripts.check_eval_numbers
```

A separate synthetic offline hosted-model feasibility experiment is documented
in `eval/AI_QA_EVAL_PLAN.md`. The final `extraction-v1` configuration used
`gpt-5.6-terra` with high reasoning to extract exact source quotes, then
compared them with the parser snapshot in deterministic code. On one fresh,
frozen 600-case synthetic evaluation it found and localized 300/300 planted
errors, raised 0/300 false alerts, and returned 599/600 valid checks. All
predeclared prototype gates passed. Live-source performance remains unmeasured,
and nothing was integrated into the product runtime.

## Environment Variables

See `.env.example` for the full list. The main product-specific settings are:

```env
DATABASE_URL=sqlite:///./data/flatfeed.db
SYNTHETIC_SEED=20260623
SYNTHETIC_LISTING_COUNT=15
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
- Optional runtime AI QA findings go only to configured admins and require
  human feedback; the public bot has no QA controls or metrics.
- The ingestion pipeline supports multiple registered source adapters; the
  public demo enables FlatFeed Synthetic only. Provider-specific adapters need
  separate source-access validation.
- User-facing listing cards are formatted in `flatfeed/matching.py`.
- Listing photos are third-party Wikimedia Commons prototype assets with separate
  attribution and license details in `assets/listing_photos/LICENSES.md`. The
  primary showcase uses an address-aligned Schlangenbader Straße 91 photo; its
  apartment details remain synthetic.
- Synthetic listing URLs (the card's `Open listing` link) point at
  `docs/demo-listing.html`, a static GitHub Pages disclosure page — not a live
  housing site. See
  `docs/PROJECT_CONTEXT.md` for the activity-check mechanics.
