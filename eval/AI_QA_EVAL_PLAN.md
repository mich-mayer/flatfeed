# Offline AI QA Evaluation Contract

**Status:** Terra-v1 high passed the one frozen validation and every
predeclared engineering, Product Scorecard, and matching-critical field gate;
locked holdout remains unopened

**Date:** 2026-07-23

**Scope:** Synthetic, offline feasibility evaluation only

## 1. Objective

This experiment will test whether an OpenAI model can detect controlled,
material errors in parser snapshots built from synthetic Berlin WBS apartment
listings.

The experiment is designed to answer one bounded question:

> Given synthetic listing text and a parser snapshot, can the model reliably
> flag whether the snapshot contains a material error and identify the affected
> field?

This is an offline feasibility experiment. It is not a production feature, a
live-source evaluation, renter research, or evidence of product impact.

## 2. Hard Product Boundary

The experiment MUST remain separate from the Telegram product runtime.

- OpenAI API access MUST NOT be added to or enabled from `main.py`.
- The experiment MUST NOT change Telegram bot behavior, deterministic parsing,
  matching, listing cards, notifications, or user filters.
- The experiment MUST NOT make AI output available to renters.
- The experiment MUST NOT write model suggestions back to listings or parser
  rules.
- The experiment runner MUST live under `eval/` and run only through an
  explicit offline command.
- The experiment credential MUST be eval-specific and MUST NOT be added
  to the bot's `.env.local` runtime configuration.
- The experiment MUST NOT modify, enable, or depend on the bot's existing
  optional admin QA provider path.

The bot's deterministic parser and matching rules remain the only owners of
user-facing decisions. A successful experiment would demonstrate technical
feasibility only; it would not authorize product integration.

## 3. Non-goals

This experiment does not:

- train, fine-tune, or distill a model;
- scrape or redistribute real housing listings;
- test live housing-provider coverage;
- measure renter demand, engagement, or outcomes;
- measure production error prevalence;
- validate autonomous parser correction;
- replace the existing deterministic parser evaluation;
- change the public case study before a locked result exists.

Prompt iteration is evaluation-driven configuration of an existing model, not
model training.

## 4. Units and Terminology

One **case** contains:

1. synthetic raw listing text;
2. the parser snapshot presented to the model;
3. hidden ground truth used only by the scorer;
4. eval-only metadata such as split, corruption field, and seed.

A **clean case** has a parser snapshot that agrees with hidden ground truth
under FlatFeed's canonical parsing semantics.

A **corrupted case** has exactly one controlled, material disagreement between
the parser snapshot and hidden ground truth.

A **model alert** is the structured-output decision that the parser snapshot
contains a material error. The output schema is implemented in
`eval/ai_qa_prompt.py`; the prompt configuration may be calibrated only on the
development set and MUST be frozen before the holdout run.

The **critical fields** are WBS, Kaltmiete, and rooms because they directly
affect the current four-field matching flow.

## 5. Dataset Contract

The experiment uses two disjoint datasets.

| Split | Clean | Corrupted | Total | Permitted use |
|---|---:|---:|---:|---|
| Development | 50 | 50 | 100 | Smoke testing, prompt iteration, threshold calibration, and reasoning-effort comparison |
| Locked holdout | 300 | 300 | 600 | One frozen final evaluation only |

Requirements for both splits:

- Cases MUST use synthetic listing data only.
- Development and holdout cases MUST be disjoint.
- Every case MUST have a stable unique ID.
- Exact model inputs MUST be unique within and across the two splits.
- Generation MUST be reproducible from recorded seeds.
- Clean and corrupted cases SHOULD cover comparable listing difficulty and
  formatting diversity.
- Hidden truth, split labels, corruption labels, case tags, and generation
  metadata MUST NOT enter raw listing text, URLs, parser input, or model prompts.

The generator, datasets, and separate answer keys were implemented in Steps
2-4. This contract defines their requirements but does not embed their data.

## 6. Controlled Error Contract

Every corrupted case MUST contain exactly one material error. Multi-error cases
are excluded from this experiment so detection and field localization remain
unambiguous.

Permitted error fields:

1. WBS
2. Kaltmiete
3. rooms
4. address or postal code
5. district
6. floor
7. Warmmiete

The 300 corrupted holdout cases MUST use this fixed distribution:

| Error field | Cases |
|---|---:|
| WBS | 75 |
| Kaltmiete | 60 |
| rooms | 50 |
| address or postal code | 40 |
| district | 30 |
| floor | 25 |
| Warmmiete | 20 |
| **Total** | **300** |

Each corruption MUST:

- change only the selected parser field;
- preserve every other ground-truth field;
- be plausible enough to represent a parser mistake;
- be detectable from the supplied listing text and parser snapshot;
- record the expected value and corrupted value in the hidden answer key;
- remain deterministic for the same seed.

Unknown or genuinely ambiguous source text MUST NOT be labeled as a definite
parser error. Such cases may be added to the clean set as difficult negative
controls only when the expected behavior is documented.

## 7. Model and Configuration Contract

The initial candidate configuration is:

| Setting | Locked starting value |
|---|---|
| Model snapshot | `gpt-5.4-mini-2026-03-17` |
| Reasoning effort | `none` |
| Input | Raw synthetic listing text plus parser snapshot |
| Output | Strict structured output |
| Temperature or sampling | Deterministic setting supported by the selected API surface |

`reasoning_effort=low` MAY be evaluated only on the development set and only if
the `none` configuration does not meet the acceptance gates after prompt
analysis.

The following MAY change during development evaluation:

- prompt wording;
- prompt version;
- structured-output schema;
- alert threshold;
- reasoning effort (`none` or `low`);
- retry policy for technical failures.

None of these may change after the configuration freeze and before scoring the
locked holdout.

Model outputs MUST remain advisory evaluation artifacts. They MUST NOT mutate
listing data, matching rules, parser rules, or user-facing output.

## 8. Ground-truth Isolation

Model input MUST contain only the information available to an actual QA review:

- raw listing text;
- parser snapshot;
- field definitions and review instructions required by the frozen prompt.

Model input MUST NOT contain:

- `clean` or `corrupted` labels;
- the corrupted field name;
- expected or original values;
- synthetic case tags;
- hidden truth fields;
- generator seeds;
- split names;
- answer-key paths;
- scoring hints derived from the answer key.

Input and answer-key artifacts MUST be stored separately. An automated leakage
check is required before any real-model run.

## 9. Metrics

All headline classification metrics use the model's frozen alert decision.

### 9.1 Listing-level error recall

```text
alerted corrupted cases / all corrupted cases
```

This measures whether the model detects that a material parser error exists,
regardless of whether it names the correct field.

### 9.2 Missed-error rate

```text
non-alerted corrupted cases / all corrupted cases
```

This equals `1 - listing-level error recall`.

### 9.3 False-alert rate

```text
alerted clean cases / all clean cases
```

### 9.4 Challenge-set precision

```text
alerted corrupted cases / all alerted cases
```

This value is valid only for the deliberately balanced challenge set. It MUST
NOT be described as production precision because the real parser-error
prevalence is unknown.

### 9.5 Field-localization accuracy

```text
alerted corrupted cases naming the correct field / alerted corrupted cases
```

### 9.6 Per-field recall

For each corruption field:

```text
cases alerted with the correct field / all cases corrupted in that field
```

### 9.7 Structured-output coverage

```text
cases with valid schema-conforming output / all attempted cases
```

A technical failure or invalid structured output counts as uncovered. For the
classification metrics, an uncovered case is treated as a non-alert: it is a
miss when the case is corrupted and not a false alert when the case is clean.
Coverage is therefore a separate hard gate and MUST be reported next to the
classification metrics.

### 9.8 Operational measurements

Record where available:

- request count and retry count;
- input, cached-input, output, and reasoning token usage;
- total USD cost and cost per completed case;
- synchronous request latency, including p50 and p95;
- batch wall-clock completion time when Batch API is used;
- technical failure categories.

Latency modes MUST NOT be mixed into one unlabeled statistic.

### 9.9 Statistical reporting

Report point estimates and Wilson 95% confidence intervals for proportions.
Do not round a failing result into a passing result.

## 10. Acceptance Gates

The frozen holdout result passes only if every gate below passes.

| Gate | Requirement |
|---|---:|
| Structured-output coverage | `>= 99.5%` |
| Overall listing-level error recall | `>= 90%` |
| WBS per-field recall | `>= 90%` |
| Kaltmiete per-field recall | `>= 90%` |
| Rooms per-field recall | `>= 90%` |
| False-alert rate | `<= 8%` |
| Challenge-set precision | `>= 85%` |
| Field-localization accuracy | `>= 90%` |

These are experiment gates, not achieved results. They MUST be labeled as
targets until the locked holdout run is complete.

Cost and latency are reported decision inputs but are not pass/fail gates in
this first feasibility experiment. The runner MUST enforce an explicit local
spending guard before paid requests.

## 11. Experiment Lifecycle

The implementation and evaluation sequence is:

1. Build and verify the synthetic case generator.
2. Build controlled corruptions and separate answer keys.
3. Generate the development and locked holdout datasets.
4. Build and test the scorer with deterministic mock predictions.
5. Build an eval-only OpenAI runner with dry-run and budget guards.
6. Run a 20-case smoke test drawn only from the development set.
7. Evaluate and iterate on all 100 development cases.
8. Freeze the complete configuration.
9. Run the 600-case locked holdout once.
10. Score, report, and decide whether the gates passed.
11. Update the case study only in a later, separately reviewed change.

Steps 1-5 MUST make no paid OpenAI calls. API credentials are needed only for
steps 6-9 and MUST remain isolated from product runtime configuration.

## 12. Configuration Freeze

Before the locked holdout is opened, record:

- model snapshot;
- reasoning effort;
- exact prompt text, version, and hash;
- exact structured-output schema and hash;
- alert threshold and scoring rule;
- retry and technical-failure policy;
- development dataset hash;
- holdout input hash;
- hidden answer-key hash;
- scorer version or source revision;
- code commit or working-tree identifier;
- pricing source and observation date used for cost calculation.

After freeze:

- prompt tuning is prohibited;
- threshold changes are prohibited;
- model or reasoning-effort changes are prohibited;
- scorer semantic changes are prohibited;
- holdout cases may not be moved into the development set.

A failed transport request may be retried only with the identical frozen input
and configuration. Retries and their reasons MUST be logged. A semantically
valid response cannot be rerun merely to seek a better answer.

## 13. Relationship to the Existing 15-case Eval

The existing `eval/run_eval.py` run over 15 authored synthetic cases remains the
deterministic parser regression check.

The new offline AI QA evaluation:

- MUST use separate datasets and result artifacts;
- MUST NOT replace or enlarge the meaning of the 15-case regression result;
- MUST NOT combine parser regression accuracy and model QA metrics into one
  denominator;
- MUST NOT change the existing public regression-case count during dataset or
  runner implementation;
- MUST keep the two evidence layers separately labeled in future reporting.

## 14. Reporting and Case-study Rules

Any future publication of this experiment MUST use the label:

> synthetic offline AI QA evaluation

Published reporting MUST state:

- the dataset is synthetic;
- the split contains 300 clean and 300 controlled-error holdout cases;
- the model and frozen configuration;
- the result applies only to this challenge set;
- challenge-set precision is not production precision;
- AI QA was not integrated into the Telegram prototype;
- no live provider listings or renter outcomes were evaluated.

Raw outputs, the frozen manifest, scoring output, and aggregate report MUST be
retained so every published number can be traced to an artifact.

The current `DESIGN_CONTENT_SYSTEM.md` permits only the 15-case authored parser
regression count as a public eval number. Therefore, publishing new AI QA
metrics later will require an explicit evidence-rule change through the
project's change-governance process. Until that separate change is approved,
new AI QA numbers remain engineering evaluation artifacts only.

If the holdout misses any gate, report the failed baseline and limitations.
Do not hide failures, select a better-looking subset, or present the experiment
as passed.

## 15. Historical Step 1 Boundary

When this contract was created, it was the only deliverable for Step 1.

Step 1 does not:

- implement a generator;
- create development or holdout data;
- create an answer key;
- change a prompt;
- call OpenAI;
- change the Telegram bot;
- change public case-study claims or numbers.

The user subsequently authorized the generator, datasets, scorer, runner, and
development-only hosted-model calibration. Those implementations and runs
remain subject to this contract; the locked holdout has not been opened.

## 16. Eval-only Runner Interface

`eval/ai_qa_runner.py` is the only runner for this experiment. It is isolated
from `main.py`, the Telegram bot, and the product's optional admin QA provider.

The safe default is a development-set dry run. It validates the dataset hash,
checks for answer-key leakage, selects cases deterministically, calculates a
conservative worst-case cost bound, and makes no network call:

```bash
.venv/bin/python -m eval.ai_qa_runner --dry-run --limit 20 \
  --max-cost-usd 0.20
```

The runner reads `OPENAI_API_KEY` only from the ignored root file
`.env.eval.local`. `--check-model` performs only an explicit availability check
for the exact configured snapshot. It never substitutes another model.

Real inference requires all of the following:

- the explicit `--execute` flag;
- a positive `--max-cost-usd` that covers the conservative preflight bound;
- an output directory inside `eval/`;
- the exact model availability check to pass.

Predictions and a redacted run manifest are written inside the selected eval
output directory. Neither artifact contains the API key or hidden answer key.
The locked holdout remains disabled in the runner until the separate
configuration-freeze step implements and verifies its release guard.

## 17. Step 7 Development Smoke-run Plan

The first hosted-model smoke run is fixed to the first 20 cases in the
development model-input artifact. Selection is deterministic and validated
against the development input hash. The dry-run summary records the selected
case IDs, exact prompt and strict output schema, model configuration, request
ceiling, budget ceiling, leakage-check result, and future artifact paths.

The initial run directory is `eval/runs/development-smoke-20/`. A dry run MUST
create no files and make no network call. A real run may write only:

- `predictions.jsonl` and `run_manifest.json` in that run directory;
- scorer reports under `eval/runs/development-smoke-20/reports/`.

The locked holdout remains unavailable. Step 7 does not verify model access and
does not execute the Responses API.

## 18. Development Calibration Record

The first 20 development cases were used for prompt and reasoning-effort
calibration. No holdout case was used. Reports contain aggregate metrics only;
the answer key remains separate from model inputs and run artifacts.

| Configuration | Recall | False-alert rate | Precision | Field localization | Coverage | Cost |
|---|---:|---:|---:|---:|---:|---:|
| `dev-v1`, `none`, 64 output tokens | 70% | 0% | 100% | 100% | 100% | $0.009861 |
| `dev-v2`, `none`, 64 output tokens | 90% | 0% | 100% | 77.8% | 100% | $0.010518 |
| `dev-v3`, `none`, 64 output tokens | 70% | 0% | 100% | 71.4% | 100% | $0.0103155 |
| `dev-v2`, `low`, 256 output tokens | 90% | 20% | 81.8% | 77.8% | 100% | $0.0194415 |

Two lower-output `low` runs were technical diagnostics only: 64 and 128 output
tokens produced incomplete responses and therefore do not support a semantic
quality comparison.

Development decision:

- retain `dev-v2` with `reasoning_effort=none` as the smoke-test candidate;
- reject `dev-v3` because both recall and field localization regressed;
- reject `reasoning_effort=low` because it did not improve recall or field
  localization and worsened false alerts, precision, cost, and latency;
- evaluate the candidate on all 100 development cases before deciding whether
  configuration freeze is justified;
- do not publish these calibration numbers in the case study.

## 19. Full Development Evaluation

All 100 development cases (50 clean and 50 corrupted) were evaluated with
`reasoning_effort=none`. The same dataset, output schema, scorer, and model
snapshot were used for every configuration below. The locked holdout remained
disabled.

| Configuration | Recall | False-alert rate | Precision | Field localization | Coverage | Cost | Gate result |
|---|---:|---:|---:|---:|---:|---:|---|
| `dev-v2` | 86% | 10% | 89.6% | 88.4% | 100% | $0.05243775 | Fail |
| `dev-v4` | 70% | 0% | 100% | 97.1% | 100% | $0.06153375 | Fail |
| `dev-v5` | 70% | 10% | 87.5% | 91.4% | 100% | $0.05520375 | Fail |

`dev-v2` remains the strongest tested baseline because it has the highest
listing-level recall while retaining acceptable challenge-set precision and
complete structured-output coverage. It still fails the development targets:

- overall recall: 86% versus the 90% target;
- false-alert rate: 10% versus the maximum 8%;
- field localization: 88.4% versus the 90% target;
- WBS recall: 76.9% versus the 90% critical-field target;
- rooms recall: 62.5% versus the 90% critical-field target.

The more explicit WBS prompts reduced false WBS localization in some cases but
made the model more conservative across unrelated fields, reducing overall
recall. This is a measured development-set trade-off, not evidence that the
model is production-ready.

Decision after full development evaluation:

- restore the exact `dev-v2` prompt as the best tested baseline;
- do not freeze the configuration;
- do not release or run the locked holdout;
- stop prompt tuning on this dataset to avoid further overfitting;
- retain all run manifests, predictions, and reports as internal synthetic
  offline evaluation artifacts;
- do not add these results to the public case study without a separate product
  and evidence review.

## 20. Luna Development Comparison

The same 100-case development set, exact `dev-v2` prompt, strict output schema,
64-token output limit, and `reasoning_effort=none` configuration were evaluated
with `gpt-5.6-luna`. No prompt or scorer semantics changed, and the locked
holdout remained disabled.

| Model | Recall | False-alert rate | Precision | Field localization | Coverage | Cost | Gate result |
|---|---:|---:|---:|---:|---:|---:|---|
| `gpt-5.4-mini-2026-03-17` | 86% | 10% | 89.6% | 88.4% | 100% | $0.05243775 | Fail |
| `gpt-5.6-luna` | 96% | 16% | 85.7% | 95.8% | 100% | $0.069917 | Fail |

Luna improved listing-level recall by 10 percentage points and field
localization by 7.4 percentage points. It reached 100% localized recall on the
development WBS and Kaltmiete corruptions. Rooms localized recall was 87.5%,
below the 90% critical-field gate. The false-alert rate increased from 10% to
16%, above the 8% maximum. These are synthetic development-set measurements,
not production accuracy estimates.

Operationally, Luna used 56,315 input and 2,267 output tokens for 100 cases,
with no reasoning tokens, retries, or technical failures. Recorded cost was
$0.069917, or $0.00069917 per case. Synchronous latency was 915 ms p50 and
3,914 ms p95. The runner used the standard short-context rates observed on
2026-07-21 and enforced a $0.25 hard limit; actual cost stayed below that
limit.

Development decision:

- keep Luna as the strongest tested error-detection candidate, but do not
  treat it as accepted because two gates failed;
- do not tune the prompt further on this development set;
- do not freeze the configuration or release the locked holdout;
- if model comparison continues, test `gpt-5.6-terra` once with the identical
  dataset, prompt, schema, output limit, and reasoning effort;
- choose between Luna and Terra only from measured quality, latency, and cost,
  not from list price alone;
- keep all Luna metrics internal until a separate public-evidence review.

## 21. Terra Development Comparison

`gpt-5.6-terra` was evaluated once on the same 100-case development set with
the exact `dev-v2` prompt, strict output schema, 64-token output limit, and
`reasoning_effort=none`. No prompt, dataset, or scorer semantics changed, and
the locked holdout remained disabled.

| Model | Recall | False-alert rate | Precision | Field localization | Coverage | Cost | Gate result |
|---|---:|---:|---:|---:|---:|---:|---|
| `gpt-5.4-mini-2026-03-17` | 86% | 10% | 89.6% | 88.4% | 100% | $0.05243775 | Fail |
| `gpt-5.6-luna` | 96% | 16% | 85.7% | 95.8% | 100% | $0.069917 | Fail |
| `gpt-5.6-terra` | 98% | 42% | 70.0% | 83.7% | 100% | $0.1749575 | Fail |

Terra found 49 of 50 corrupted cases, but alerted on 21 of 50 clean cases. Its
42% false-alert rate, 70% challenge-set precision, 83.7% field-localization
accuracy, and 87.5% rooms localized recall all failed their gates. The higher
listing-level recall does not compensate for this loss of specificity and
localization. These are synthetic development-set measurements, not production
accuracy estimates.

Operationally, Terra used 56,315 input and 2,278 output tokens for 100 cases,
with no reasoning tokens, retries, or technical failures. Recorded cost was
$0.1749575, or approximately $0.001750 per case. Synchronous latency was 975 ms
p50 and 2,270 ms p95. The runner enforced a $0.60 hard limit; actual cost stayed
below that limit.

Development decision:

- reject Terra for this experiment because it is more expensive than Luna and
  materially worse on false alerts, precision, and field localization;
- retain Luna as the best tested balance, but do not mark it accepted because
  its false-alert and rooms gates still fail;
- do not escalate to Sol merely because a higher-priced tier exists;
- do not tune the prompt further or reuse this development set for another
  selection round;
- do not freeze a configuration or release the locked holdout;
- the next experiment, if continued, should first address evaluation design or
  obtain a fresh development set rather than selecting a better-looking result
  from repeated runs on the current cases.

## 22. Luna-specific Prompt Calibration on Fresh Data

Two new 100-case synthetic splits were generated with seeds `20260723` and
`20260724`. Each contains 50 clean and 50 corrupted cases with the development
error distribution. They are disjoint from each other and from the original
development and locked-holdout model inputs. The locked answer key was not
read, no holdout inference occurred, and no original dataset artifact was
modified.

The first split was used once to evaluate `luna-v1`. That prompt was a narrow
adaptation of `dev-v2`: it made the supported WBS-tier normalization and the
priority of explicit Berlin `Bezirk` wording explicit. The result was:

| Split and prompt | Recall | False-alert rate | Precision | Field localization | Coverage | Cost | Gate result |
|---|---:|---:|---:|---:|---:|---:|---|
| calibration, `luna-v1` | 96% | 2% | 98.0% | 97.9% | 100% | $0.092243 | Fail |

All aggregate gates passed except WBS localized recall: 84.6% versus the 90%
critical-field target. Calibration diagnostics showed one bounded ambiguity in
the instructions: the prompt did not state explicitly that a single numeric
WBS means exactly one tier, that a generic WBS is not equivalent to a numeric
tier, or that named floor values such as `Hochparterre` are distinct from a
numeric floor.

Those three measured gaps produced the frozen `luna-v2` prompt. It was then
evaluated once on the previously unused second split; no further prompt changes
were made from that result:

| Split and prompt | Recall | False-alert rate | Precision | Field localization | Coverage | Cost | Gate result |
|---|---:|---:|---:|---:|---:|---:|---|
| validation, `luna-v2` | 100% | 8% | 92.6% | 94.0% | 100% | $0.100727 | Fail |

`luna-v2` passed the overall recall, false-alert, precision, field-localization,
WBS, rooms, and structured-output gates. It failed Kaltmiete localized recall:
80% versus the 90% critical-field target. The errors were detected at listing
level but two were assigned to the wrong field. The 100-case sample also leaves
wide per-field Wilson intervals, so a point estimate alone is insufficient for
a production-quality claim.

Operationally, `luna-v2` used 87,143 input and 2,264 output tokens, with no
reasoning tokens, retries, invalid outputs, or technical failures. Recorded
cost was $0.100727, or $0.00100727 per case. Synchronous latency was 920 ms p50
and 2,460 ms p95. The `luna-v1` and `luna-v2` real runs cost $0.192970 in total.

Decision after Luna-specific calibration:

- keep `gpt-5.6-luna` with `reasoning_effort=none` as the best cost/quality
  candidate tested so far;
- preserve both prompts and both reports so the iteration remains auditable;
- do not tune against the validation split or select a better-looking subset;
- do not freeze the configuration and do not release the locked holdout because
  one critical-field gate still fails;
- if the experiment continues, improve the evaluation design with a new
  predeclared calibration/validation cycle and more critical-field examples;
- keep all results labeled as synthetic offline evaluation and do not convert
  them into production, user-impact, or parser-accuracy claims.

## 23. Predeclared Final Luna-v3 Cycle

One final prompt-calibration cycle is permitted before any holdout decision.
It consists of exactly one new prompt version, one calibration run, and, only
if calibration passes every acceptance gate, one frozen validation run. No
prompt change is permitted after validation results are known.

Both new splits contain 200 unique cases: 100 clean and 100 corrupted. Each
corrupted case contains exactly one controlled material error. The predeclared
error distribution in both splits is:

| Field | Corrupted cases |
|---|---:|
| Kaltmiete | 25 |
| WBS | 20 |
| rooms | 15 |
| floor | 15 |
| address/postal code | 10 |
| district | 8 |
| Warmmiete | 7 |

Seeds are `20260725` for calibration and `20260726` for validation. Both splits
must be disjoint from each other, the original development and locked-holdout
model inputs, and the earlier Luna calibration/validation inputs. The locked
truth remains unread and no locked-holdout inference is permitted.

The only new prompt is `luna-v3`. It preserves the `luna-v2` WBS, district,
room, and floor rules and adds a narrow rent-localization rule measured from
the preceding cycle: Kaltmiete/Grundmiete/Nettokaltmiete map only to
`rent_kalt`, while Warmmiete/Bruttowarmmiete/Gesamtmiete map only to
`rent_warm`. The model remains `gpt-5.6-luna` with
`reasoning_effort=none`, strict Structured Outputs, 64 output tokens, and no
retries.

The acceptance gates remain unchanged. If calibration misses any gate, stop
without using validation. If calibration passes, freeze the exact model,
prompt hash, schema, reasoning, token limit, and runner settings before the one
validation run. Release of the 600-case locked holdout requires validation to
pass every gate; it is not automatic and remains a separate explicit step.

### Final Luna-v3 results

The 200-case calibration run passed every acceptance gate:

| Metric | Calibration result | Gate |
|---|---:|---:|
| Error recall | 99% | at least 90% |
| False-alert rate | 5% | at most 8% |
| Challenge-set precision | 95.2% | at least 85% |
| Field localization | 98.0% | at least 90% |
| Kaltmiete localized recall | 92% | at least 90% |
| WBS localized recall | 100% | at least 90% |
| rooms localized recall | 100% | at least 90% |
| Structured-output coverage | 100% | at least 99.5% |

The exact passing configuration was frozen before validation. Calibration used
199,450 input and 4,519 output tokens, cost $0.226564, and had no retries,
invalid outputs, or technical failures. Synchronous latency was 963 ms p50 and
4,638 ms p95.

The same frozen configuration was then run once on the previously unused
200-case validation split:

| Metric | Validation result | Gate result |
|---|---:|---|
| Error recall | 95% | Pass |
| False-alert rate | 3% | Pass |
| Challenge-set precision | 96.9% | Pass |
| Field localization | 98.9% | Pass |
| Kaltmiete localized recall | 100% | Pass |
| WBS localized recall | 85% | **Fail** |
| rooms localized recall | 100% | Pass |
| Structured-output coverage | 100% | Pass |

Validation used 199,484 input and 4,509 output tokens, cost $0.226538, and had
no retries, invalid outputs, or technical failures. Synchronous latency was
909 ms p50 and 8,364 ms p95. The calibration and validation runs together cost
$0.453102 for 400 cases.

Final decision for this cycle:

- `luna-v3` materially improved Kaltmiete localization and passed seven of the
  eight predeclared gates on independent validation;
- the configuration is not accepted because WBS localized recall was 85%,
  below the 90% critical-field threshold;
- no prompt change is permitted from the validation result;
- the locked holdout remains disabled and must not be run;
- Luna remains a promising low-cost feasibility candidate, but this experiment
  does not justify a production-quality or general parser-accuracy claim;
- any future attempt must be a separately authorized experiment with a new
  hypothesis and new predeclared datasets, not another iteration on these
  calibration or validation cases.

## 24. Authorized Luna-v4 WBS Semantic-Drift Cycle

This separately authorized cycle tests one measured hypothesis from the
Luna-v3 validation failure: Luna missed exact lower-bound semantics in three
WBS cases where `141-220` should exclude tier `140`. The QA model must remain
an independent semantic cross-check of parser output. No deterministic WBS
rule is used as the evaluator and no AI call is integrated into product
runtime.

The cycle permits exactly one new prompt version, `luna-v4`, one calibration
run, and, only if calibration passes every existing acceptance gate, one
frozen validation run. The model configuration is `gpt-5.6-luna`,
`reasoning_effort=none`, strict Structured Outputs, 64 output tokens, and zero
retries. The prompt adds a literal boundary-preservation check: it must not
round or snap stated bounds to supported WBS tiers and must distinguish
inclusive lower bounds from `greater than` wording.

Calibration and validation each contain 240 new unique cases: 120 clean and
120 cases with exactly one controlled material error. Each listing uses new,
semantically equivalent WBS wording that differs from the base generator's
canonical labels. The predeclared error distribution for each split is:

| Field | Corrupted cases |
|---|---:|
| WBS | 50 |
| Kaltmiete | 20 |
| rooms | 15 |
| address/postal code | 10 |
| district | 10 |
| floor | 8 |
| Warmmiete | 7 |

Seeds are `20260727` for calibration and `20260728` for validation. Both
splits must be reproducible, mutually disjoint, and disjoint from the original
development and locked-holdout inputs and all prior Luna cycle inputs. Model
inputs remain separate from truth files.

The existing acceptance gates remain unchanged. If calibration misses any
gate, the cycle stops without validation. If calibration passes, the exact
model, prompt hash, output schema, reasoning, token limit, retries, runner
version, validation input hash, and hard budget must be frozen before the one
validation run. No prompt change is permitted after validation results are
known.

The 600-case locked holdout remains unopened, disabled in the runner, and
outside this cycle. Even if frozen validation passes every gate, using the
locked holdout is a separate next step requiring an explicit release decision.

### Luna-v4 calibration result

The one permitted 240-case calibration run completed with strict structured
output on every case and no technical failures, but it did not pass the
acceptance contract:

| Metric | Calibration result | Gate result |
|---|---:|---|
| Error recall | 97.5% | Pass |
| False-alert rate | 15.8% | **Fail** |
| Challenge-set precision | 86.0% | Pass |
| Field localization | 88.9% | **Fail** |
| Kaltmiete localized recall | 80% | **Fail** |
| WBS localized recall | 96% | Pass |
| rooms localized recall | 80% | **Fail** |
| Structured-output coverage | 100% | Pass |

All 19 false alerts were localized to WBS. Eleven of the 13 wrong-field
localizations also selected WBS: three district, two floor, two Kaltmiete, two
Warmmiete, and two rooms errors were misclassified as WBS. This is evidence of
a salience side effect from the new WBS-focused prompt and semantic-drift
wording, not evidence that the overall checker improved.

The run used 287,967 input and 5,434 output tokens, cost $0.320571, and had no
retries, invalid structured outputs, or technical failures. Synchronous
latency was 1,030 ms p50 and 3,015 ms p95.

Decision:

- stop this cycle at calibration because the overall gate status is `fail`;
- do not create a Luna-v4 configuration freeze and do not run its validation;
- keep the locked holdout unopened and disabled;
- do not publish Luna-v4 as a successful model result;
- before another paid run, audit the new WBS language variants and the prompt's
  field-order bias, then predeclare a fresh balanced cycle with clean WBS
  negative controls and new calibration/validation data.

## 25. Luna-v4 Failure Audit and Final Luna-v5 Recovery Contract

The reproducible aggregate audit confirms that Luna-v4 failed through a narrow
numeric-range effect, not a general inability to understand WBS:

- all 19 clean false alerts predicted WBS;
- 11 of 13 wrong-field localizations were diverted to WBS;
- clean cases with `No WBS required`, `WBS required, type unknown`, exact WBS
  100, and the 100/140 set produced zero false alerts;
- the 19 false alerts were concentrated in the 100-180, 140-220, and 141-220
  normalized range families;
- both WBS localized misses occurred in the exact WBS 100 family, showing that
  stronger range instructions alone do not solve all WBS cases.

One wording variant is removed from future data because it mixes an
`Einkommensgrenze` boundary with a WBS tier and is not sufficiently natural for
an objective challenge case. The remaining variants must state either a
plausible source-style range, an exact supported-tier set, or an unambiguous
inclusive/exclusive bound. This adjudication changes future synthetic data
only; it does not relabel or rescore Luna-v4.

One final Luna recovery cycle is permitted. If it fails, stop prompt tuning for
Luna and report the model's measured limitation or compare a stronger model on
a separately authorized dataset. Do not create Luna-v6 by default.

The `luna-v5` prompt removes the mandatory WBS-first instruction. It preserves
the established rent, room, district, and floor rules, states that
`display_wbs` is a normalized set rather than a literal transcription, and
adds symmetric controls for correct and incorrect 140/141 lower boundaries.
It requires all seven fields to be compared independently before selecting the
single directly contradicted field.

Calibration and validation each contain 280 new unique cases: 140 clean and
140 with exactly one controlled material error. The seven expected WBS
semantic families are balanced in each split. Every family contributes 20
clean negative controls, eight WBS-corrupted cases, and twelve cases corrupted
in a non-WBS field. The predeclared corrupted distribution per split is:

| Field | Corrupted cases |
|---|---:|
| WBS | 56 |
| Kaltmiete | 21 |
| rooms | 21 |
| address/postal code | 14 |
| district | 10 |
| floor | 10 |
| Warmmiete | 8 |

Seeds are `20260729` for calibration and `20260730` for validation. Both
splits must be reproducible, mutually disjoint, and disjoint from the original
development and locked holdout inputs and every earlier Luna cycle. The model
configuration remains `gpt-5.6-luna`, `reasoning_effort=none`, strict
Structured Outputs, 64 output tokens, and zero retries.

All existing acceptance gates remain unchanged. Run calibration once. Freeze
the exact configuration and permit the single validation run only if every
calibration gate passes. The 600-case locked holdout remains disabled and is a
separate release decision even after a passing validation.

### Luna-v5 offline preflight

The two 280-case splits were generated and verified with zero overlap against
each other and every prior model-input split. Calibration model-input SHA-256
is `e2d2179034fc622644dfb4e5bc4a7e2510fdd4675012eb28baa1a0c12f9691dd`;
validation model-input SHA-256 is
`c4009fd9faa87d3966361fa6aa435c826bf13f2e153ba7143d6e3d3445decdcd`.

The calibration dry-run used prompt SHA-256
`da470e9499139e0a00c3a21c7dbb5bc9c72af484472542dcc8f83946de86efad`
and the existing strict-output schema SHA-256
`f7c5d21b7ee06ff3647c4726253c74eeccecd250ec96c7275d07f70d24989945`.
It scheduled 280 case requests, zero retries, and one availability check. The
conservative worst-case bound is $1.389674, covered by a $1.40 hard budget.
No credential was read and no OpenAI call was made during this preflight.

### Final Luna-v5 calibration result

The one permitted 280-case calibration run completed with 100% structured
output coverage and no technical failures. Seven of eight gates passed:

| Metric | Calibration result | Gate result |
|---|---:|---|
| Error recall | 90.7% | Pass |
| False-alert rate | 3.6% | Pass |
| Challenge-set precision | 96.2% | Pass |
| Field localization | 96.9% | Pass |
| Kaltmiete localized recall | 95.2% | Pass |
| WBS localized recall | 80.4% | **Fail** |
| rooms localized recall | 100% | Pass |
| Structured-output coverage | 100% | Pass |

The balanced design removed the broad WBS-salience failure: false alerts fell
from 19/120 clean cases in Luna-v4 to 5/140 in Luna-v5, and wrong-field
localizations fell from 13 to 4. However, Luna missed 11 of 56 WBS errors. The
misses were distributed across exact WBS 100 (3/8), WBS 100/140 (4/8), WBS up
to 180 (2/8), no-WBS (1/8), and generic-WBS (1/8). It missed none of the eight
141-220 or eight 140-220 WBS corruptions. This falsifies the narrower belief
that lower-bound semantics were the remaining general WBS blocker: Luna's
residual failure is detecting several close normalized-set changes.

The run used 341,084 input and 6,305 output tokens and cost $0.378914. It had
zero retries, invalid outputs, or technical failures. Synchronous latency was
1,026 ms p50 and 2,890 ms p95.

Final Luna decision:

- overall calibration status is `fail`; do not freeze this configuration;
- do not run Luna-v5 validation and do not open the locked holdout;
- do not create Luna-v6 by default or claim that Luna meets the experiment's
  acceptance contract;
- retain Luna as evidence of a low-cost model with strong general metrics but
  insufficient critical-field WBS recall under this task definition;
- the next model step, if authorized, is a predeclared comparison with a
  stronger model on a new calibration/validation split, not further Luna
  prompt tuning.

## 26. Authorized Luna Reasoning-Effort Screen

Before paying for a stronger model, one small Luna configuration screen is
authorized to test a variable not measured in the final Luna cycles:
`reasoning_effort=low`. This is not prompt tuning, training, validation, or a
new acceptance claim. It compares inference effort on new development cases.

The screen contains 24 new unique cases:

- eight clean controls with correct but difficult WBS range normalization;
- ten cases with one controlled WBS error, concentrated in the exact and close
  normalized-set classes Luna-v5 missed;
- six cases with one controlled non-WBS error and a correct WBS range as a
  distractor, one for each other field.

Seed is `20260731`. The cases must be disjoint from every previous model-input
split, including the original development and locked holdout. Inputs and truth
remain separate, and the locked holdout truth is not read.

The exact same 24 inputs and frozen `luna-v5` prompt are run once with each
configuration:

1. `gpt-5.6-luna`, `reasoning_effort=none`, 256 max output tokens, zero retries;
2. `gpt-5.6-luna`, `reasoning_effort=low`, 256 max output tokens, zero retries.

Using the same output limit isolates reasoning effort and avoids treating
reasoning-token truncation as a quality result. The screen does not use the
standard acceptance gates because its composition is intentionally diagnostic
and its sample is small.

`low` advances only if all of the following predeclared criteria are met:

- 100% structured-output coverage and zero technical failures;
- at least two more correctly localized WBS errors than `none`;
- no increase in clean false alerts;
- no decrease in correctly localized non-WBS errors;
- no decrease in total case-level correctness.

If `low` fails any criterion, Luna testing stops and no further Luna dataset or
validation run is created. If `low` passes, it only becomes the candidate for
a separately predeclared fresh calibration; this 24-case screen cannot count
as calibration or validation evidence. No Sol call and no locked-holdout call
is authorized by this screen.

The generated model-input SHA-256 is
`fd67995f81ec616fd630c854fa326eb2a6374f0aa27b8d9e6f26daa2d9d5d1ed`.
Both dry-runs schedule 24 requests and have the same conservative worst-case
bound of $0.146716 because the prompt, inputs, and 256-token output cap are
identical. Each run therefore has a $0.15 hard budget; the combined hard limit
is $0.30. No API call was made during dataset generation or dry-run.

### Luna reasoning-screen result

Both configurations completed all 24 development cases with 100% structured
output coverage, zero retries, and zero technical failures:

| Diagnostic measure | `none` | `low` |
|---|---:|---:|
| Correctly localized WBS errors | 7/10 | 10/10 |
| Clean false alerts | 2/8 | 0/8 |
| Correctly localized non-WBS errors | 5/6 | 6/6 |
| Total case-level correctness | 18/24 | 24/24 |

The paired result contains 18 cases both configurations answered correctly and
six cases only `low` answered correctly; there are no cases only `none`
answered correctly. Therefore `low` passes every predeclared advancement
criterion.

The `none` run used 29,248 input and 544 output tokens and cost $0.032512.
The `low` run used the same 29,248 input tokens plus 1,269 output tokens,
including 688 reasoning tokens, and cost $0.036862. Combined screen cost was
$0.069374, below the $0.30 combined hard limit. Latency increased from 1,042 ms
to 1,256 ms p50 and from 2,392 ms to 2,672 ms p95.

Decision: advance `gpt-5.6-luna` with `reasoning_effort=low` only to a fresh,
separately predeclared calibration contract. The 24 screen cases cannot be
reused in that calibration. No validation, Sol, or locked-holdout inference is
authorized by this result.

## 27. Fresh Luna-low Calibration and Validation Contract

The reasoning screen authorizes one new independent Luna cycle. Its bounded
hypothesis is that `reasoning_effort=low` can preserve the Luna-v5 prompt's
specificity while improving detection of close normalized WBS-set errors on a
larger, balanced challenge set. The 24 diagnostic screen cases are excluded
from both new splits and do not count as calibration or validation evidence.

Calibration and validation each contain 280 new unique cases: 140 clean and
140 with exactly one controlled material error. The seven Luna-v5 WBS semantic
families remain balanced in each split. Every family contributes 20 clean
negative controls, eight WBS-corrupted cases, and twelve cases corrupted in a
non-WBS field. The corrupted distribution in each split is unchanged:

| Field | Corrupted cases |
|---|---:|
| WBS | 56 |
| Kaltmiete | 21 |
| rooms | 21 |
| address/postal code | 14 |
| district | 10 |
| floor | 10 |
| Warmmiete | 8 |

Seeds are `20260801` for calibration and `20260802` for validation. Both
splits must be byte-reproducible, mutually disjoint, and disjoint from the
original development and locked-holdout inputs, all earlier Luna cycle inputs,
and the 24 reasoning-screen inputs. Model inputs and truth remain separate.

The exact model configuration is:

| Setting | Frozen calibration value |
|---|---|
| Model | `gpt-5.6-luna` |
| Reasoning effort | `low` |
| Prompt | `luna-v5` |
| Output | strict Structured Outputs |
| Maximum output tokens | 256 |
| Retries | 0 |
| Service tier | `default` |

No prompt, schema, scorer, threshold, or dataset-composition change is allowed
after this contract. The runner must use all 280 calibration cases once, write
to the single canonical calibration run directory, and refuse to overwrite an
existing run. Before the real call it must pass dataset verification, leakage
and overlap tests, a no-network dry-run, and a model availability check. The
calibration hard budget is `$1.72`; execution is prohibited if the
conservative preflight bound exceeds it or if a different hard limit is
supplied.

### Luna-low offline preflight

The generated calibration model-input SHA-256 is
`e84e630f2c6d882536d60c26067d8ee7b2c9f9f39e859543ea6205858248aaf1`;
the validation model-input SHA-256 is
`42d97d06077946ec8f01b36d0cb62fd362080b6119cab359ebf8416112a6a389`.
All recorded exact-input overlap counts are zero, including overlap with the
24 reasoning-screen inputs and the locked holdout inputs.

The calibration dry-run used prompt SHA-256
`da470e9499139e0a00c3a21c7dbb5bc9c72af484472542dcc8f83946de86efad`
and strict-output schema SHA-256
`f7c5d21b7ee06ff3647c4726253c74eeccecd250ec96c7275d07f70d24989945`.
It schedules 280 case requests, zero retries, and one model-availability check.
The conservative worst-case bound is `$1.712380`, covered by the exact `$1.72`
hard budget. No credential was read and no OpenAI call was made during this
dry-run.

The acceptance gates in section 10 remain unchanged. Calibration is run and
scored first. If any gate fails, stop without creating a configuration freeze
and without using validation. If every gate passes, record a configuration
freeze containing the exact model, reasoning effort, prompt and schema hashes,
runner version, scorer semantics, dataset hashes, retry policy, token limit,
pricing observation, validation input hash, and one-run validation budget.
Validation remains disabled until that freeze exists and is verified; it is
not authorized for the current calibration step.

The 600-case locked holdout remains unopened and disabled. Sol and Terra are
outside this cycle. Nothing in this contract changes `main.py`, Telegram, the
product runtime, public case-study metrics, or the deterministic 15-case parser
regression evidence.

### Final Luna-low calibration result

The one permitted 280-case calibration run completed with strict structured
output on every case, zero retries, and zero technical failures. Seven of the
eight acceptance gates passed:

| Metric | Calibration result | Gate result |
|---|---:|---|
| Error recall | 94.3% | Pass |
| False-alert rate | 0.0% | Pass |
| Challenge-set precision | 100.0% | Pass |
| Field localization | 100.0% | Pass |
| Kaltmiete localized recall | 100.0% | Pass |
| WBS localized recall | 89.3% | **Fail** |
| rooms localized recall | 100.0% | Pass |
| Structured-output coverage | 100.0% | Pass |

WBS localized recall was 50/56. The 90% gate requires at least 51/56, so the
unrounded result fails by one correctly localized WBS case. The other two
missed corrupted cases were one address/postal-code case and one district
case. No clean case produced a false alert, and no alerted corrupted case was
localized to the wrong field.

The run used 341,114 input tokens and 12,345 output tokens, including 5,740
reasoning tokens. Recorded cost was `$0.415184`, below the `$1.72` hard limit.
Synchronous latency was 1,172 ms p50 and 2,689 ms p95.

Decision:

- overall calibration status is `fail`; do not create a configuration freeze;
- do not run the Luna-low validation split and do not open the locked holdout;
- do not rerun calibration or tune against these 280 calibration cases;
- retain the new validation split unopened for auditability, not as permission
  for a later selective run;
- any further model step requires a separately authorized hypothesis and
  contract; Sol and Terra remain untested in this cycle;
- keep the result labeled as synthetic offline AI QA evaluation and do not
  integrate it into `main.py`, Telegram, matching, or public product metrics.

### Luna-low aggregate failure audit

A reproducible post-run audit was generated without any new model call. It
contains no case IDs, raw listing text, or parser snapshots and uses only the
completed calibration inputs, truth, predictions, and the prior Luna-v5
aggregate audit.

The eight false negatives consist of six WBS cases, one address/postal-code
case, and one district case. The WBS misses are not concentrated in the
numeric lower-bound families that motivated the earlier Luna-v4 work:

- four of six WBS misses occur in the `No WBS required` or generic
  `WBS required, type unknown` semantic families;
- the `100, 140`, `140, 160, 180, 220`, and `160, 180, 220` families have zero
  misses across 24 WBS-corrupted cases;
- the six WBS misses span six distinct expected-to-corrupted transitions, one
  miss per transition;
- `wbs_range_boundary_shift` records 2 misses in 37 cases, while the smaller
  presence/specificity subtypes account for the other four misses; those small
  subtype counts are diagnostic slices, not independent performance estimates.

Across different fresh calibration datasets, Luna-v5 with `none` had 11/56
WBS localized misses, 5/140 clean false alerts, and four wrong-field
localizations; Luna-v5 with `low` had 6/56, 0/140, and zero respectively. This
is descriptive cross-cycle context, not a paired causal estimate of reasoning
effort.

The audit does not identify one narrow, repeated transition that would justify
another prompt patch. The stop decision is unchanged: do not tune on these
cases, rerun calibration, freeze the configuration, or run validation. The
next decision is to close Luna with the measured WBS limitation or separately
authorize a stronger-model experiment with a new hypothesis and new data.

## 28. Authorized Terra Reasoning-Effort Screen

Terra was previously evaluated only with `reasoning_effort=none`. On the
original 100-case development set it reached 98% error recall but produced a
42% false-alert rate, 70% challenge-set precision, 83.7% field localization,
and 87.5% rooms localized recall. That result rejects the tested Terra-none
configuration, but it does not measure Terra with additional reasoning.

Luna's paired 24-case screen showed that `reasoning_effort=low` can materially
change specificity and localization. Before paying for Sol, one paired Terra
screen is therefore authorized to isolate the same configuration variable on
new data. This is a development diagnostic, not calibration, validation, or a
new acceptance claim.

The screen contains 48 new unique cases:

- 16 clean controls spanning no-WBS, generic-WBS, exact-tier, and normalized
  range families;
- 20 cases with exactly one controlled WBS error, emphasizing presence,
  specificity, and close normalized-set changes;
- 12 cases with exactly one controlled non-WBS error and a correct WBS
  distractor, two cases for each other field.

Seed is `20260803`. Inputs and truth must remain separate. The 48 model inputs
must be disjoint from the original development and locked-holdout inputs,
every Luna calibration/validation cycle, the 24-case Luna reasoning screen,
and both unused and used Luna-low splits.

The exact same inputs and frozen prompt are run once with each configuration:

1. `gpt-5.6-terra`, `reasoning_effort=none`;
2. `gpt-5.6-terra`, `reasoning_effort=low`.

Both use prompt `luna-v5`, strict Structured Outputs, 256 maximum output
tokens, zero retries, `service_tier=default`, and the same scorer semantics.
Using the same inputs and output limit isolates reasoning effort; the prompt
name records its provenance and does not imply a Luna-only API feature.

Terra-low advances to a separately predeclared fresh calibration contract only
if all criteria pass:

- 100% structured-output coverage and zero technical failures;
- at least 18/20 correctly localized WBS errors;
- at most 1/16 clean false alerts;
- at least 11/12 correctly localized non-WBS errors;
- at least 44/48 total case-level correct results;
- no lower total correctness than Terra-none.

The screen's enriched composition means its rates are diagnostic only. If low
fails any criterion, stop Terra and do not create Terra calibration or
validation data. If low passes, the screen still cannot count as calibration
or validation evidence. Sol, Luna-low validation, and the locked holdout are
not authorized by this screen.

Each run has an exact `$0.80` hard budget; the combined hard limit is `$1.60`.
Execution is prohibited unless the generated-data verification, leakage and
overlap tests, exact configuration guards, model availability check, and
no-network dry-runs all pass and the conservative bound for each run is within
its hard limit. No credential may be persisted in any artifact.

### Terra screen offline preflight

The generated model-input SHA-256 is
`3208360094cadf99a712ba014d82fa9fcf826be6317e183d362def00d368e5eb`;
the separate truth SHA-256 is
`d40c727d13b4f133afa93695e8b745e0b226651cdf5cb2e64815aebd6b9717f0`.
Every recorded overlap count is zero, including Luna-low calibration and its
unused validation split.

Both dry-runs used prompt SHA-256
`da470e9499139e0a00c3a21c7dbb5bc9c72af484472542dcc8f83946de86efad`
and strict-output schema SHA-256
`f7c5d21b7ee06ff3647c4726253c74eeccecd250ec96c7275d07f70d24989945`.
Each schedules 48 case requests, zero retries, and one availability check. The
conservative worst-case bound is `$0.733735` per run, covered by the exact
`$0.80` per-run hard limit and `$1.60` combined limit. No credential was read
and no OpenAI call was made during generation or dry-run.

### Terra reasoning-screen result

Both configurations completed all 48 development cases with 100% structured
output coverage, zero retries, zero clean false alerts, and zero technical
failures:

| Diagnostic measure | `none` | `low` |
|---|---:|---:|
| Correctly localized WBS errors | 16/20 | 17/20 |
| Clean false alerts | 0/16 | 0/16 |
| Correctly localized non-WBS errors | 10/12 | 10/12 |
| Total case-level correctness | 42/48 | 43/48 |

The paired outcomes contain 41 cases both configurations answered correctly,
two cases only `low` answered correctly, one case only `none` answered
correctly, and four cases both answered incorrectly. `low` therefore improves
net total correctness by one case but does not meet three predeclared absolute
criteria:

- WBS localization is 17/20, below the required 18/20;
- non-WBS localization is 10/12, below the required 11/12;
- total correctness is 43/48, below the required 44/48.

The `none` run used 58,405 input and 1,080 output tokens and cost `$0.1622125`.
The `low` run used the same 58,405 input tokens plus 1,761 output tokens,
including 642 reasoning tokens, and cost `$0.1724275`. Combined cost was
`$0.334640`, below the `$1.60` combined hard limit. Latency increased from
1,080 ms to 1,261 ms p50 and from 2,409 ms to 2,832 ms p95.

Decision:

- Terra `low` is confirmed to execute successfully with the Responses API, but
  it does not pass the diagnostic advancement contract;
- stop Terra and do not create Terra calibration or validation datasets;
- do not tune the prompt or rerun either Terra configuration on these cases;
- keep Luna-low validation and the locked holdout unopened;
- Sol was not used and remains a separate, explicitly predeclared next-model
  decision rather than an automatic escalation.

### Terra aggregate failure audit

A reproducible aggregate-only audit was generated from the frozen 48-case
inputs, separate truth, and the completed `none` and `low` predictions. The
artifact contains no case IDs, raw listing text, parser snapshots, or exact
field values. It made no new model call and does not authorize prompt tuning,
a screen rerun, calibration, validation, or locked-holdout access.

Terra-low's five misses split across two failed fields:

- WBS: 3/20 misses, one each in `wbs_specificity_confusion`,
  `wbs_range_boundary_shift`, and `wbs_requirement_added`;
- address/postal code: 2/2 misses, both `postal_code_substitution`.

Both address/postal-code cases were also missed by Terra-none. For WBS, the
paired result contains two `low`-only corrections, one `none`-only correction,
and two cases both configurations missed. Thus additional reasoning changes
individual WBS decisions but does not resolve a single repeated WBS failure
mode.

The audit supports the possibility that prompt behavior contributes to the
postal-code failures. It does not support one narrow Terra-specific prompt
change: the failed advancement gates span address/postal-code and WBS, and the
three WBS misses span three different corruption subtypes. A change intended
to repair both gates would be multi-axis and tuned to this development screen.

Decision remains `stop_terra`: do not edit the prompt and rerun Terra against
these 48 cases. The next experiment, if authorized, is a separately
predeclared Sol reasoning/configuration screen on fresh inputs with zero
overlap with the Terra screen. Sol remains unrun at this point.

## 29. Authorized Terra Prompt × Reasoning Screen

The aggregate audit permits a new hypothesis on new data; it does not permit
rerunning the prior 48 cases. One paired 2×2 development screen is authorized
to separate prompt and reasoning effects for `gpt-5.6-terra`:

| Profile | Prompt | Reasoning effort |
|---|---|---|
| A | `luna-v5` | `low` |
| B | `terra-v1` | `low` |
| C | `luna-v5` | `medium` |
| D | `terra-v1` | `medium` |

`terra-v1` is a task-general inspection protocol. It requires a source-to-
snapshot pass across all seven fields, independent street/house-number/postal-
code comparison, and separate WBS presence, specificity, and normalized-set
checks. It contains no exact values, text, or case IDs from the prior Terra
failures.

The screen uses 48 fresh cases generated with seed `20260819`: 16 clean, 20
WBS-corrupted, and 12 non-WBS-corrupted cases, with two cases for every other
field. Model inputs and truth remain separate. The input SHA-256 is
`ef02b258ea795b386b778f724bd3adf35fb879104bc775ca669d606a35f88dac`;
truth SHA-256 is
`48f0ef7f76dc410a4428858846724fc651cfa1eb81471254842ef11162fe999c`.
All recorded exact-input overlap counts are zero, including the locked
holdout, every Luna dataset, and the first 48-case Terra screen.

Every profile uses strict Structured Outputs, 256 maximum output tokens, zero
retries, `service_tier=default`, and identical scorer semantics. Prompt hashes
are `da470e9499139e0a00c3a21c7dbb5bc9c72af484472542dcc8f83946de86efad`
for `luna-v5` and
`672629d914d73cde056968c0249ae14b522703987d632f967eee866496d8f6c9`
for `terra-v1`. The strict-output schema hash is
`f7c5d21b7ee06ff3647c4726253c74eeccecd250ec96c7275d07f70d24989945`.

A profile is eligible for a separately predeclared fresh calibration only if
all absolute criteria pass:

- 100% structured-output coverage and zero technical failures;
- at least 18/20 correctly localized WBS errors;
- at most 1/16 clean false alerts;
- at least 11/12 correctly localized non-WBS errors;
- at least 44/48 total case-level correct results.

If multiple profiles pass, select by total correctness, WBS correctness,
non-WBS correctness, fewer false alerts, lower observed cost, then profile ID.
If none passes, stop Terra. No result from this development screen is itself
calibration or validation evidence.

Dry-run bounds are `$0.733695` for each `luna-v5` profile and `$0.831375`
for each `terra-v1` profile. Each arm has an exact `$0.90` hard budget and the
combined hard limit is `$3.60`. Each arm schedules 48 case calls, zero retries,
and one exact-model availability check. Dry-run read no credential and made no
network call. Execution is prohibited if any artifact, hash, profile, output
directory, or budget differs from this contract.

The locked holdout, Luna-low validation, calibration, and Sol remain disabled.
Nothing in this experiment modifies `main.py`, Telegram, matching, or public
product metrics.

### Terra Prompt × Reasoning result

All four frozen profiles ran once on the same 48 fresh development cases with
zero retries. Results were:

| Profile | WBS | Clean false alerts | Non-WBS | Total | Coverage | Cost |
|---|---:|---:|---:|---:|---:|---:|
| `luna-v5-low` | 17/20 | 0/16 | 11/12 | 44/48 | 97.9% | `$0.1716175`* |
| `terra-v1-low` | 20/20 | 0/16 | 12/12 | 48/48 | 100% | `$0.203820` |
| `luna-v5-medium` | 18/20 | 0/16 | 11/12 | 45/48 | 100% | `$0.171435` |
| `terra-v1-medium` | 20/20 | 0/16 | 12/12 | 48/48 | 100% | `$0.197040` |

`luna-v5-low` had one `response_incomplete` technical failure; its recorded
usage and cost are therefore partial for 47/48 completed responses. The other
profiles had zero technical failures. Combined recorded cost was `$0.7439125`,
below the `$3.60` hard limit.

At `low`, changing `luna-v5` to `terra-v1` produced four right-only correct
cases and no left-only correct cases. At `medium`, it produced three
right-only correct cases and no left-only correct cases. With `terra-v1`, the
`low` and `medium` outputs were both correct on all 48 cases, so this screen
shows a prompt gain but no measured quality gain from higher reasoning once
the Terra-specific inspection protocol is present. With `luna-v5`, `medium`
had three medium-only correct cases, two low-only correct cases, and one case
both missed.

Three profiles pass every absolute gate: `terra-v1-low`,
`terra-v1-medium`, and `luna-v5-medium`. The two `terra-v1` profiles tie on
all quality metrics and false alerts. Under the predeclared observed-cost
tie-break, `terra-v1-medium` ranks first (`$0.197040` versus `$0.203820` in
this screen). This single observed cost ordering is not a general claim that
medium is cheaper.

Decision: advance `gpt-5.6-terra`, `reasoning_effort=medium`, prompt
`terra-v1` only to a separately predeclared fresh calibration contract. Do not
reuse these 48 cases, do not treat the 48/48 result as calibration evidence,
and do not run validation or the locked holdout. Sol remains unrun.

## 30. Authorized Terra-v1 Medium Calibration

The selected 2×2 profile advances to one independent calibration run. The
frozen configuration is `gpt-5.6-terra`, `reasoning_effort=medium`, prompt
`terra-v1`, strict Structured Outputs, 256 maximum output tokens, zero
retries, and `service_tier=default`.

Two reproducible 280-case splits were generated with separate model inputs and
truth:

- calibration seed `20260820`, input SHA-256
  `83474873c20f7d5231ec3523492bdbfc03a9e99364c1933775918a187c0fd335`,
  truth SHA-256
  `fa4e08574a12349898d72430328a6e4d2b2ea070705f19c94f6c3c4f926f8043`;
- validation seed `20260821`, input SHA-256
  `1b6dabc602067d571adf42b6a0e467293503ac4802eb4910974dcba0663f58e2`,
  truth SHA-256
  `2ddfb4d1db958e3963aced37f1b706668a9ea9c82992878910f1933dde6934f4`.

Each split contains 140 clean and 140 single-error cases. The error
distribution and WBS semantic balance match the prior 280-case calibration
contract: 56 WBS, 21 Kaltmiete, 21 rooms, 14 address/postal-code, 10 district,
10 floor, and 8 Warmmiete cases. All
recorded exact-input overlaps are zero between the two splits and against the
locked holdout, every Luna dataset, and both Terra development screens. No
development-screen case is reused.

Calibration uses the unchanged gates from section 10: error recall at least
90%, clean false-alert rate at most 8%, challenge precision at least 85%,
field localization at least 90%, WBS/Kaltmiete/rooms localized recall at least
90%, and structured-output coverage at least 99.5%. Every gate must pass.

The prompt SHA-256 is
`672629d914d73cde056968c0249ae14b522703987d632f967eee866496d8f6c9`;
the strict schema SHA-256 is
`f7c5d21b7ee06ff3647c4726253c74eeccecd250ec96c7275d07f70d24989945`.
The no-network dry-run schedules 280 case requests, zero retries, and one exact
model-availability check. Its conservative worst-case bound is `$4.850250`,
covered by the exact `$5.00` calibration hard budget. The dry-run did not read
the credential.

Only calibration is authorized now. If any gate fails, stop without a freeze
or validation. If all gates pass, create and verify a configuration freeze
containing the exact model, effort, prompt/schema hashes, runner/scorer
semantics, dataset hashes, retry policy, output limit, observed pricing, and a
separate validation budget. The runner rejects validation before that freeze.

The locked holdout, Sol, and every previous unused validation split remain
disabled. This cycle is synthetic offline AI QA only and does not modify the
product runtime or public metrics.

### Terra-v1 Medium calibration result and freeze

The one authorized 280-case calibration completed with zero retries, zero
technical failures, and 100% structured-output coverage. All eight gates
passed:

| Metric | Result | Gate |
|---|---:|---|
| Error recall | 134/140, 95.7% | Pass |
| Clean false-alert rate | 0/140, 0.0% | Pass |
| Challenge precision | 134/134, 100.0% | Pass |
| Field localization | 134/134, 100.0% | Pass |
| WBS localized recall | 53/56, 94.6% | Pass |
| Kaltmiete localized recall | 21/21, 100.0% | Pass |
| rooms localized recall | 19/21, 90.5% | Pass |
| Structured-output coverage | 280/280, 100.0% | Pass |

The six false negatives were three WBS, two rooms, and one district case. No
alerted case was localized to the wrong field and no clean case produced an
alert.

The run used 385,885 input tokens and 11,634 output tokens, including 5,019
reasoning tokens. Recorded cost was `$1.1392225`, below the `$5.00` hard
limit. Synchronous latency was 1,141 ms p50 and 2,678 ms p95.

Because every gate passed, a configuration freeze was created for exactly one
validation run. It fixes `gpt-5.6-terra`, `reasoning_effort=medium`,
`terra-v1`, 256 output tokens, zero retries, runner version `1.5`, strict
schema and prompt hashes, calibration evidence hashes, and validation input
hash. The validation worst-case bound is `$4.850310`, covered by an exact
`$5.00` hard budget. The freeze does not authorize the locked holdout.

Validation was not executed in this step. The next authorized action is one
frozen 280-case Terra validation run; no prompt, scorer, dataset, model,
reasoning, retry, or output-limit change is permitted beforehand.

## 31. Pre-validation Product Scorecard Contract

The engineering scorer and all frozen acceptance gates remain unchanged. A
separate Product Scorecard translates the same scored predictions into four
plain-language metrics for the portfolio case. It is a reporting and product
decision layer only: it cannot change predictions, truth, the frozen scorer,
the Terra configuration, or validation inputs.

The four scorecard metrics and targets are fixed before validation:

| Product metric | Formula | Target | 280-case validation rule |
|---|---|---:|---:|
| Parser Error Detection Rate | alerted corrupted cases / all corrupted cases | `>= 95%` | at least 133/140 |
| False Alert Rate | alerted clean cases / all clean cases | `<= 3%` | at most 4/140 |
| Correct Field Detection Rate | corrupted cases naming the correct field / all corrupted cases | `>= 90%` | at least 126/140 |
| Successful Check Rate | valid schema-conforming responses / all attempted cases | `>= 99.5%` | at least 279/280 |

Correct Field Detection Rate deliberately uses every corrupted case as its
denominator. It is therefore stricter and easier to explain than the existing
conditional field-localization metric, which uses only already-detected
corrupted cases.

The detailed scorecard reports all evaluated fields in this product order:
WBS, district, Kaltmiete, rooms, address/postal code, floor, and Warmmiete.
WBS, district, Kaltmiete, and rooms are matching-critical. Each has a separate
`>= 90%` internal guardrail. The critical-field guardrails are publication
conditions and case-study diagnostics, not additional landing-page headline
metrics. District is included even though the historical engineering scorer
did not give it a hard per-field gate.

A positive landing claim is permitted only when:

- the source run is the one exact `terra_validation` run authorized by
  `eval/runs/terra-calibration-configuration-freeze.json`;
- the run manifest matches the frozen model, prompt, reasoning, input hash,
  retry policy, output limit, and hard budget;
- every unchanged engineering acceptance gate passes;
- all four Product Scorecard metrics pass;
- all four matching-critical field guardrails pass.

The landing may then show only the four simple Product Scorecard results, each
with its percentage and absolute count. They must appear below the primary
renter-product story and carry the same-depth label `Synthetic frozen
validation`. The detailed field table, confidence intervals, cost, latency,
and historical engineering metrics stay in the case study or eval artifacts.
Calibration output is labeled `Synthetic calibration preview` and is never
landing evidence.

The public limitation must state that this synthetic validation does not
measure live housing-provider listings or real parser-error prevalence. A real
product would still require human review of every AI alert and an independent
random sample of listings that received no alert; otherwise missed parser
errors cannot be measured. FlatFeed does not currently use housing-provider
data without permission, so this real-world audit workflow is a considered
future control, not prototype functionality. Listings never collected by a
source are also outside this checker and require a separate future
source-coverage control.

`eval/ai_qa_product_scorecard.py` implements this separate layer. It consumes
only the aggregate scorer report and redacted run manifest, requires the exact
configuration freeze for validation, emits aggregate-only JSON and Markdown,
and refuses to overwrite existing scorecard artifacts. It does not read the
credential, model inputs, raw listing text, parser snapshots, or answer key.
Validation remained unexecuted while this contract and implementation were
verified. Section 32 records the subsequent one-time frozen run.

## 32. Terra-v1 Medium Frozen Validation Result

The one validation run authorized by
`eval/runs/terra-calibration-configuration-freeze.json` completed on
2026-07-23. The runner used the frozen `gpt-5.6-terra` configuration with
`reasoning_effort=medium`, prompt `terra-v1`, strict Structured Outputs, 256
maximum output tokens, zero retries, and runner version `1.5`. The input,
prompt, and schema hashes matched the freeze. The locked holdout remained
disabled.

All 280 cases completed with valid structured outputs and no technical
failures. The Product Scorecard results were:

| Product metric | Result | Target | Status |
|---|---:|---:|---:|
| Parser Error Detection Rate | 134/140, 95.7% | `>= 95%` | Pass |
| False Alert Rate | 1/140, 0.7% | `<= 3%` | Pass |
| Correct Field Detection Rate | 134/140, 95.7% | `>= 90%` | Pass |
| Successful Check Rate | 280/280, 100.0% | `>= 99.5%` | Pass |

The detailed field results were:

| Field | Correct field | Role | Guardrail |
|---|---:|---|---:|
| WBS | 53/56, 94.6% | matching-critical | Pass |
| district | 10/10, 100.0% | matching-critical | Pass |
| Kaltmiete | 21/21, 100.0% | matching-critical | Pass |
| rooms | 18/21, 85.7% | matching-critical | **Fail** |
| address/postal code | 14/14, 100.0% | diagnostic | n/a |
| floor | 10/10, 100.0% | diagnostic | n/a |
| Warmmiete | 8/8, 100.0% | diagnostic | n/a |

The model missed six corrupted cases: three rooms mismatches and three WBS
mismatches. The rooms misses were direct neighboring-value contradictions
(`4` versus `3.5`, `4` versus `5`, and `3.5` versus `2.5`). The WBS misses
were two lower-bound exclusions (`141-220` or greater than `140`) and one
explicit no-WBS-required listing paired with a generic WBS snapshot. One
clean exact-`WBS 100` case produced a false alert. Every emitted corrupted-case
alert named the correct field.

The unchanged engineering contract also failed because rooms recall was below
its `>= 90%` gate. Therefore the final Product Scorecard decision is `fail`
even though all four simple aggregate metrics passed. The configuration is not
accepted, and `positive_landing_claim_allowed` is false. No hosted-model metric
block may be added to the landing from this run.

The validation-case requests used 385,807 input tokens and 12,367 output
tokens, including 5,719 reasoning tokens. The recorded validation-case cost was
`$0.42491725`, with no retries; the separate model-availability check is not
included in that recorded run cost. Synchronous latency was 1,139 ms p50 and
2,689 ms p95.

This validation split is now consumed. It must not be rerun, used for prompt
selection, or reopened as a new acceptance attempt. The locked holdout remains
closed. Any further hosted-model work requires a new development hypothesis,
fresh non-overlapping development data, and—if that hypothesis advances—a new
calibration and validation pair.

## 33. Authorized Terra-v2 Prompt Screen

The failed frozen validation authorizes failure analysis, not reuse of its
cases. A new development-only paired screen tests one task-general prompt
hypothesis: an explicit source equality ledger and a final rooms/WBS
contradiction veto may reduce direct comparison misses without increasing
false alerts.

The two profiles are:

| Profile | Model | Prompt | Reasoning |
|---|---|---|---|
| Baseline | `gpt-5.6-terra` | `terra-v1` | `medium` |
| Candidate | `gpt-5.6-terra` | `terra-v2` | `medium` |

Model, reasoning, cases, schema, output limit, retry policy, and scorer stay
identical, so the only experimental variable is the prompt. `terra-v2` adds no
case IDs, addresses, exact validation values, or hidden answer-key content. It
requires an internal seven-row equality ledger, exact half-room comparison,
explicit no-WBS precedence, and a final contradiction veto before returning
`has_error=false`.

The screen uses 64 fresh synthetic cases generated with seed `20260822`: 16
clean and 48 single-error cases. The corrupted distribution is 20 rooms, 20
WBS, 2 Kaltmiete, 2 address/postal-code, 2 district, 1 floor, and 1 Warmmiete.
The exact model-input SHA-256 is
`2fd5fe9250eed90fbec0f533e970715b946c1d7bc2c8e93a262e0cc8a354b7e8`;
the separate truth SHA-256 is
`d3b0f9b543124348846e4c5f9adcf2af075783123960e03d70eb3ab858d425cb`.
Recorded exact-input overlap is zero against every prior dataset, including
the consumed Terra calibration/validation pair and the locked holdout.

Both profiles use strict Structured Outputs, 256 maximum output tokens, zero
retries, `service_tier=default`, and runner version `1.5`. Prompt hashes are
`672629d914d73cde056968c0249ae14b522703987d632f967eee866496d8f6c9`
for `terra-v1` and
`e8282bd83ba0f9ba49721d2148e880990fe2c8e19cf6d209263c649518065428`
for `terra-v2`. The schema hash remains
`f7c5d21b7ee06ff3647c4726253c74eeccecd250ec96c7275d07f70d24989945`.

The candidate advances only if every absolute criterion passes:

- 100% structured-output coverage and zero technical failures;
- at least 19/20 correctly identified rooms errors;
- at least 19/20 correctly identified WBS errors;
- at most 1/16 clean false alerts;
- at least 7/8 correctly identified errors in the other fields;
- at least 61/64 total case-level correct results.

It must also beat the baseline on rooms by at least one correct case, with no
regression in WBS, clean false alerts, or the other fields. Equal results do
not justify changing the prompt.

The no-network dry-run bounds are `$1.108660` for `terra-v1` and `$1.253940`
for `terra-v2`. Each arm has an exact `$1.50` hard budget; the combined hard
limit is `$3.00`. Each arm schedules 64 case calls, zero retries, and one exact
model-availability check. Dry-run read no credential and made no network call.

This is development evidence only. It cannot repair or replace the failed
frozen validation. If `terra-v2` advances, it requires completely new
calibration and validation data before any acceptance or landing claim. The
consumed validation, locked holdout, Sol, product runtime, and public metrics
remain untouched.

### Terra-v2 prompt-screen result

Both frozen prompt arms ran once on the same 64 fresh cases with zero retries,
zero technical failures, 100% structured-output coverage, and no clean false
alerts:

| Profile | rooms | WBS | Other fields | Clean false alerts | Total | Cost |
|---|---:|---:|---:|---:|---:|---:|
| `terra-v1-medium` | 19/20 | 19/20 | 8/8 | 0/16 | 62/64 | `$0.0941435` |
| `terra-v2-medium` | 20/20 | 17/20 | 6/8 | 0/16 | 59/64 | `$0.09834825` |

The paired comparison contains 58 cases both prompts answered correctly, one
case both missed, four cases only `terra-v1` answered correctly, and one case
only `terra-v2` answered correctly. The candidate fixed the baseline's one
rooms miss, but newly missed two `141-220` WBS boundary contradictions, one
explicit district contradiction, and one postal-code contradiction. Both
prompts missed the same remaining WBS case.

`terra-v2` therefore failed three absolute gates: WBS, other fields, and total
correctness. It also failed the predeclared no-regression criteria for WBS and
other fields. Decision: `stop_terra_v2_prompt_change`. Do not advance this
prompt, tune it against these cases, or create a new calibration from it.

Combined recorded cost was `$0.19249175`, below the `$3.00` combined hard
limit. The baseline used 1,291 reasoning tokens and the candidate used 1,108.
The consumed validation, locked holdout, Sol, product runtime, and public
metrics were not used or changed.

## 34. Authorized Terra Medium vs High Reasoning Screen

The failed frozen validation and stopped Terra-v2 prompt experiment leave one
unmeasured Terra configuration variable: whether `reasoning_effort=high`
improves direct comparison accuracy while the stronger `terra-v1` prompt stays
unchanged. This is a development diagnostic, not a calibration rerun,
validation repair, or new acceptance claim.

The paired profiles are:

| Profile | Model | Prompt | Reasoning |
|---|---|---|---|
| Baseline | `gpt-5.6-terra` | `terra-v1` | `medium` |
| Candidate | `gpt-5.6-terra` | `terra-v1` | `high` |

The screen uses 48 fresh synthetic cases generated with seed `20260823`: 12
clean and 36 cases with exactly one controlled material error. The corrupted
distribution is 14 WBS, 14 rooms, 2 Kaltmiete, 2 district, 2 address/postal
code, 1 floor, and 1 Warmmiete. Model inputs and truth remain separate. The
exact inputs must have zero overlap with every prior model-input split,
including the consumed Terra calibration and validation, the Terra-v2 screen,
and the locked holdout.

Both profiles use strict Structured Outputs, 256 maximum output tokens, zero
retries, `service_tier=default`, and identical scorer semantics. Model,
prompt, cases, schema, output limit, retry policy, and service tier remain
identical, so reasoning effort is the only experimental variable.

`high` advances only if every absolute criterion passes:

- 100% structured-output coverage and zero technical failures;
- at least 13/14 correctly identified rooms errors;
- at least 13/14 correctly identified WBS errors;
- at most 1/12 clean false alerts;
- at least 7/8 correctly identified errors in the other fields;
- at least 45/48 total case-level correct results.

It must also produce at least one more correct case than `medium`, including at
least one additional correct WBS-or-rooms case, with no regression in WBS,
rooms, clean false alerts, or the other fields. Equal results do not justify
the higher reasoning setting.

Each arm has an exact `$1.00` hard budget and the combined hard limit is
`$2.00`. Execution is prohibited unless generation verification, leakage and
overlap tests, exact configuration guards, model availability, and no-network
dry-runs all pass and the conservative bound for each arm is within its hard
limit. No credential may be persisted in any artifact.

### Terra medium-vs-high offline preflight

The generated model-input SHA-256 is
`4a8ea0a67fbe914121fba8f552f58a779a2bdc83abc121ac52957d06a71b737c`;
the separate truth SHA-256 is
`5421a74fadf833357399f7f1696953b0feaf32a82e608517b4c424ed4bc27dea`.
Every recorded exact-input overlap count is zero, including the consumed
Terra validation, the Terra-v2 prompt screen, and the locked holdout.

Both dry-runs used `terra-v1` prompt SHA-256
`672629d914d73cde056968c0249ae14b522703987d632f967eee866496d8f6c9`
and strict-output schema SHA-256
`f7c5d21b7ee06ff3647c4726253c74eeccecd250ec96c7275d07f70d24989945`.
Each schedules 48 case requests, zero retries, and one exact-model
availability check. The conservative worst-case bound is `$0.8315275` per
arm, covered by the exact `$1.00` per-arm hard budget and `$2.00` combined
limit. No credential was read and no OpenAI call was made during generation
or dry-run.

This screen cannot reuse or repair the consumed validation. If `high`
advances, it requires completely new calibration and validation datasets
before any acceptance or landing claim. If it does not advance, stop Terra
configuration work; the next model experiment may compare Sol on fresh data
under a separately predeclared contract. The locked holdout, product runtime,
and public metrics remain untouched.

### Terra medium-vs-high reasoning-screen result

Both profiles completed all 48 development cases with 100% structured-output
coverage, zero retries, zero technical failures, and no clean false alerts:

| Profile | rooms | WBS | Other fields | Clean false alerts | Total | Cost |
|---|---:|---:|---:|---:|---:|---:|
| `terra-v1-medium` | 12/14 | 14/14 | 8/8 | 0/12 | 46/48 | `$0.07084225` |
| `terra-v1-high` | 14/14 | 14/14 | 8/8 | 0/12 | 48/48 | `$0.08740375` |

The paired comparison contains 46 cases both profiles answered correctly, two
cases only `high` answered correctly, no cases only `medium` answered
correctly, and no cases both missed. Both high-only corrections were rooms
neighbor-value contradictions. Therefore `high` passes every absolute and
comparative advancement criterion.

`medium` used 66,163 input tokens and 2,205 output tokens, including 1,059
reasoning tokens. `high` used the same 66,163 input tokens and 2,947 output
tokens, including 1,773 reasoning tokens. Combined recorded cost was
`$0.158246`, below the `$2.00` combined hard limit. Median synchronous latency
increased from 1,140 ms to 1,283 ms; p95 increased from 1,650 ms to 3,206 ms.

Decision: advance `gpt-5.6-terra`, `reasoning_effort=high`, prompt `terra-v1`
only to a separately predeclared fresh calibration contract. Do not reuse
these 48 cases, the failed frozen validation, or any prior calibration or
validation data. This development screen is not landing evidence and does not
authorize validation, the locked holdout, Sol, or product-runtime integration.

## 35. Authorized Terra-v1 High Calibration Contract

The medium-versus-high development screen selected one configuration for an
independent calibration: `gpt-5.6-terra`, `reasoning_effort=high`, prompt
`terra-v1`, strict Structured Outputs, 256 maximum output tokens, zero
retries, and `service_tier=default`.

Two new reproducible splits are required:

- 280-case calibration generated with seed `20260824`;
- 280-case validation generated with seed `20260825`.

Each split contains 140 clean and 140 cases with exactly one controlled
material parser error. The corrupted distribution remains product-aligned:

| Field | Corrupted cases |
|---|---:|
| WBS | 56 |
| Kaltmiete | 21 |
| rooms | 21 |
| address/postal code | 14 |
| district | 10 |
| floor | 10 |
| Warmmiete | 8 |

The seven WBS semantic families remain balanced. Model inputs and truth are
stored separately. Both splits must be mutually disjoint and have zero exact
input overlap with the locked holdout, every Luna dataset, every prior Terra
screen, the consumed Terra medium calibration and validation, and the 48-case
medium-versus-high screen.

Only calibration is authorized in this step. It advances only if all unchanged
engineering gates in section 10 pass and all Product Scorecard conditions
below pass on calibration:

- Parser Error Detection Rate at least 95%;
- False Alert Rate at most 3%;
- Correct Field Detection Rate at least 90%;
- Successful Check Rate at least 99.5%;
- WBS, district, Kaltmiete, and rooms correct-field recall each at least 90%.

If any condition fails, stop without a configuration freeze or validation
run. If every condition passes, create and verify a freeze containing the
exact model, reasoning effort, prompt and schema hashes, runner and scorer
semantics, calibration evidence, validation input hash, retry policy, output
limit, pricing observation, and a one-run validation hard budget.

Before any paid request, generation verification, leakage tests, overlap
tests, no-network dry-run, exact-model availability, and a fixed calibration
hard budget must all pass. The exact hashes and budget are recorded below
after generation and before execution. Validation remains rejected by the
runner until a passing calibration freeze exists.

This cycle is synthetic offline feasibility evidence only. It does not reuse
the failed validation, open the locked holdout, run Sol, modify the product
runtime, or authorize a landing claim.

### Terra-v1 high offline preflight

The generated calibration model-input SHA-256 is
`5e0906d7fd4158724b23ac9670cc01f575e1d11d6c1aef4999f90d34676a3199`;
its separate truth SHA-256 is
`1a121da6067b67b01df7ac575bf8f8d18eb9bdef6512f21e7d8ec03db2486571`.
The generated validation model-input SHA-256 is
`fb26a15e4e4489c82dec342449f44dc8df18daed7bf6c71f5d6d3a8c3c6a4f65`;
its separate truth SHA-256 is
`58cdbea6704a62696a43ca53ca7935ec5c7835d348ed85bd2efc414fe6274ee2`.

All recorded exact-input overlap counts are zero, including
calibration-versus-validation, the locked holdout, the consumed Terra medium
calibration and validation, the Terra-v2 prompt screen, and the 48-case
medium-versus-high reasoning screen.

The calibration dry-run used prompt SHA-256
`672629d914d73cde056968c0249ae14b522703987d632f967eee866496d8f6c9`
and strict-output schema SHA-256
`f7c5d21b7ee06ff3647c4726253c74eeccecd250ec96c7275d07f70d24989945`.
It schedules 280 case requests, zero retries, and one exact-model availability
check. The conservative worst-case bound is `$4.85015`, covered only by the
exact `$5.00` calibration hard budget. Dry-run read no credential, made no
network call, and created no run artifact.

At preflight, the known API balance did not guarantee the full worst-case
ceiling after recorded subsequent spend, so no paid call was made in that
step. The user subsequently explicitly authorized proceeding because the
expected overrun risk was considered minimal; the `$5.00` local hard limit and
all other frozen settings remained unchanged. Validation remained disabled
until the passing calibration freeze recorded below.

### Terra-v1 high calibration result and freeze

The one authorized 280-case calibration completed with zero retries. It
produced 279 valid strict structured outputs and one technical
`response_incomplete` on a rooms-corrupted case. The predeclared 99.5%
Successful Check Rate permits one uncovered case, so both the engineering and
Product Scorecard contracts pass:

| Product metric | Result | Target | Status |
|---|---:|---:|---:|
| Parser Error Detection Rate | 139/140, 99.3% | `>= 95%` | Pass |
| False Alert Rate | 0/140, 0.0% | `<= 3%` | Pass |
| Correct Field Detection Rate | 139/140, 99.3% | `>= 90%` | Pass |
| Successful Check Rate | 279/280, 99.6% | `>= 99.5%` | Pass |

The detailed field results were:

| Field | Correct field | Role | Guardrail |
|---|---:|---|---:|
| WBS | 56/56, 100.0% | matching-critical | Pass |
| district | 10/10, 100.0% | matching-critical | Pass |
| Kaltmiete | 21/21, 100.0% | matching-critical | Pass |
| rooms | 20/21, 95.2% | matching-critical | Pass |
| address/postal code | 14/14, 100.0% | diagnostic | n/a |
| floor | 10/10, 100.0% | diagnostic | n/a |
| Warmmiete | 8/8, 100.0% | diagnostic | n/a |

Challenge-set precision and conditional field localization were both 100%.
All semantic model decisions with valid output were correct; the only missed
error was the technical incomplete response.

The 279 usage-bearing responses used 384,471 input tokens and 16,814 output
tokens, including 9,982 reasoning tokens. Recorded case cost was `$0.490998`;
it is marked partial because the incomplete response supplied no usage record.
Synchronous latency was 1,295 ms p50 and 3,524 ms p95.

Because every predeclared condition passed, the exact configuration was frozen
in `eval/runs/terra-high-configuration-freeze.json`. The freeze fixes
`gpt-5.6-terra`, `reasoning_effort=high`, `terra-v1`, strict schema, 256 output
tokens, zero retries, runner version `1.5`, calibration evidence hashes, and
validation input SHA-256
`fb26a15e4e4489c82dec342449f44dc8df18daed7bf6c71f5d6d3a8c3c6a4f65`.
The one-run validation worst-case bound is `$4.850265`, covered by an exact
`$5.00` hard budget.

Validation was not executed in this step. The freeze does not authorize the
locked holdout, product integration, or a landing claim.

## 36. Terra-v1 High Frozen Validation Result

The one authorized frozen validation was executed exactly once against the
previously generated 280-case validation split. Preflight verified the frozen
model-input SHA-256
`fb26a15e4e4489c82dec342449f44dc8df18daed7bf6c71f5d6d3a8c3c6a4f65`,
280 cases, `gpt-5.6-terra`, `reasoning_effort=high`, prompt `terra-v1`,
strict Structured Outputs, 256 maximum output tokens, zero retries, and the
`$5.00` hard budget. The run did not change the frozen configuration.

All 280 requests returned valid schema-conforming outputs. The Product
Scorecard results were:

| Product metric | Result | Target | Status |
|---|---:|---:|---:|
| Parser Error Detection Rate | 139/140, 99.3% | `>= 95%` | Pass |
| False Alert Rate | 1/140, 0.7% | `<= 3%` | Pass |
| Correct Field Detection Rate | 139/140, 99.3% | `>= 90%` | Pass |
| Successful Check Rate | 280/280, 100.0% | `>= 99.5%` | Pass |

The detailed field results were:

| Field | Correct field | Role | Guardrail |
|---|---:|---|---:|
| WBS | 56/56, 100.0% | matching-critical | Pass |
| district | 10/10, 100.0% | matching-critical | Pass |
| Kaltmiete | 21/21, 100.0% | matching-critical | Pass |
| rooms | 20/21, 95.2% | matching-critical | Pass |
| address/postal code | 14/14, 100.0% | diagnostic | n/a |
| floor | 10/10, 100.0% | diagnostic | n/a |
| Warmmiete | 8/8, 100.0% | diagnostic | n/a |

The model missed one rooms error and raised one WBS alert on a clean case. It
never named the wrong field after detecting a corrupted case: conditional
field localization was 139/139, or 100%. Challenge-set precision was 139/140,
or 99.3%. All unchanged engineering gates and all matching-critical field
guardrails passed.

The run used 385,850 input tokens and 16,787 output tokens, including 9,942
reasoning tokens. Recorded cost was `$0.49132475`. Synchronous latency was
1,235 ms p50 and 3,547 ms p95. No retry was attempted.

The aggregate-only Product Scorecard is stored in
`eval/runs/terra-high-validation/product-scorecard/`. Its exact freeze check
passed and `positive_landing_claim_allowed` is true. This permits only the four
simple metrics above to appear on the landing under the label `Synthetic
frozen validation`, with absolute counts and the real-world manual-audit
limitation at the same reading depth.

This result accepts the configuration only for synthetic offline feasibility.
It does not show performance on live housing-provider listings or natural
parser-error prevalence. A real product would still need human review of every
alert plus a random sample of no-alert listings. The validation is consumed
and must not be rerun or used for prompt tuning. The locked holdout remains
unopened, Sol was not run, and the product runtime remains unchanged.
