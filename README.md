# FlatFeed

FlatFeed is a working Telegram prototype for reducing repeated checks across
Berlin WBS listings. A user saves one four-field filter and requests matching
listings in one consistent card. Automatic delivery is implemented and sends
each new match once when enabled; it is disabled in the default prototype.

The catalog is synthetic. This self-directed portfolio project does not provide
live housing coverage or measured user outcomes. WBS (Wohnberechtigungsschein)
is a certificate used to qualify for subsidized housing in Berlin; Kaltmiete is
the base rent, excluding operating and heating costs.

[Read the case study](https://mich-mayer.github.io/flatfeed/case-study.html)
· [Read the final synthetic evaluation](eval/runs/extraction-v1-final-600/report.md)
· [Run locally](#run-locally)

## What is implemented

- One saved filter: WBS type, district, maximum Kaltmiete, and rooms.
- Rule-based parsing and matching. Missing values required by a filter do not
  produce a match.
- Up to three matches on demand, each in a consistent Telegram card with
  estimated walks to the nearest S- and U-Bahn stations.
- Filter editing, reset, and confirmed deletion of saved FlatFeed data.
- A background collection and notification loop with duplicate-send prevention,
  available through `BOT_BACKGROUND_ENABLED=true`.

The source-adapter registry, ingestion history, activity checks and source-health
monitoring are exercised through one synthetic adapter. No live housing-company
adapters or scraping are included. The card's `Open listing` action opens a
[synthetic disclosure page](https://mich-mayer.github.io/flatfeed/demo-listing.html).

## Product decisions and contribution

The [case study's My role section](CASE_STUDY.md#my-role) records the author's
work on the user problem, product scope, matching rules, missing-data policy,
AI boundary and evaluation criteria. The Telegram prototype was implemented
with Claude Code and Codex as coding collaborators.

The key decisions were to test mechanics with generated listings, use rules for
user-facing matches, and evaluate AI only as a conditional quality check for
text-based source data. Complete, reliable structured feeds could map directly
into the common listing format; access terms and provider formats remain
unvalidated.

## What was evaluated

A separate offline `extraction-v1` experiment used `gpt-5.6-terra` with high
reasoning to extract exact source quotes from raw listing text. Code compared
those quotes with the parser snapshot and produced review flags. On one frozen
600-case synthetic evaluation, the check found and localized 300/300 planted
errors, raised 0/300 false alerts, and returned 599/600 usable checks. There were
no retries or tuning after the run. Live-source performance remains unmeasured.

This evaluated configuration is **not integrated into the Telegram runtime**.
The codebase also contains a separate optional admin-only runtime QA path,
disabled by default, that receives text and a parser snapshot and returns a
risk assessment. The 600-case results do not validate that runtime path.
Neither path can change listing data or user-facing matches automatically.

Start with the [evaluation guide](eval/README.md), the
[final protocol](eval/AI_QA_EVAL_PLAN.md), or the
[Markdown case study](CASE_STUDY.md). Earlier unsuccessful experiments remain
available as clearly identified history.

## Repository map

| Location | Purpose |
|---|---|
| [docs/](docs/) | Case-study site sources and project documentation; only allowlisted site files are deployed |
| [flatfeed/](flatfeed/) | Parser, matching, database, ingestion, transit estimates and optional runtime QA |
| [main.py](main.py) | Telegram saved-filter flow and conditional background delivery |
| [synthetic/](synthetic/) | Generated prototype listings and hidden regression truth |
| [eval/](eval/README.md) | Offline evaluation code, datasets, frozen results and experiment history |
| [tests/](tests/) | Product and evaluation regression checks |
| [scripts/](scripts/) | Database setup, synthetic ingestion, public-evidence checks and Pages staging |
| [data/](data/README.md) | Bundled transit stations and provenance |
| [assets/listing_photos/](assets/listing_photos/LICENSES.md) | Prototype photos and third-party attribution |

## Run locally

CI uses Python 3.12. Create an environment and install the pinned dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env.local
```

Set `TELEGRAM_BOT_TOKEN` in `.env.local` to a token for your own test bot, then:

```bash
ENV_FILE=.env.local python scripts/init_db.py
ENV_FILE=.env.local python scripts/ingest_synthetic.py
ENV_FILE=.env.local python main.py
```

`/start` opens the filter home. The command menu contains `/start`, `/filter`,
`/matches`, `/help`, and `/delete`. The catalog is disclosed as synthetic at
entry and in `/help`. No public hosted-bot access is needed to read the case study.

See [.env.example](.env.example) for configuration. The default database is
local SQLite; automatic delivery and runtime AI QA are disabled. OpenAI
credentials are optional and are not needed for deterministic matching or the
default regression checks. Keep credentials and local databases untracked.

## Development checks

In a **fresh disposable checkout**, prepare the ignored deterministic fixture
files before the test suite, as CI does. This reconstructs local test fixtures;
it does not call a model or create new acceptance evidence. Do not use this
step to regenerate or retest a consumed research dataset in a working
experiment directory.

```bash
ENV_FILE=/dev/null python -m eval.ai_qa_datasets
ENV_FILE=/dev/null python -m unittest discover -s tests
ENV_FILE=/dev/null python -m eval.run_eval
ENV_FILE=/dev/null python -m scripts.check_eval_numbers
git diff --check
```

15 authored synthetic cases currently pass the parser regression check. This
is a development check, separate from the frozen hosted-model experiment.
For machine-readable local diagnostics, run `python -m eval.run_eval --json`.
Do not rerun the consumed model evaluations to verify documentation changes.

Build a site-only staging directory for inspection or deployment:

```bash
python -m scripts.stage_pages /tmp/flatfeed-pages-preview
python -m http.server 8000 --directory /tmp/flatfeed-pages-preview
```

The destination must be new. The builder copies only the site's explicit file
allowlist; project notes, experiment data and retired captures are excluded.

## Data and asset credits

Transit estimates use a static station extract attributed to **VBB Verkehrsverbund
Berlin-Brandenburg GmbH**. See [data provenance and license information](data/README.md)
for the source, transformation and limits of the recorded snapshot provenance.
Listing photos have their own [authors, licenses and modification details](assets/listing_photos/LICENSES.md).
The showcase photo depicts Schlangenbader Straße 91; apartment availability and
terms remain synthetic. The repository's [MIT license](LICENSE) covers project
code; third-party data and photos retain their respective terms.

## Contributing and project context

Read [AGENTS.md](AGENTS.md) or [CLAUDE.md](CLAUDE.md), then the
[design and content system](DESIGN_CONTENT_SYSTEM.md),
[product context](docs/PROJECT_CONTEXT.md), [current status](docs/CURRENT_STATUS.md)
and [working rules](docs/agent-workflow.md). These documents define the product
boundaries and verification requirements for changes.
