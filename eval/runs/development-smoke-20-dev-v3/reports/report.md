# Synthetic offline AI QA evaluation

Engineering evaluation artifact. Results apply only to this synthetic challenge set and are not production precision or user-impact evidence.
This offline scorer does not integrate OpenAI or AI QA into the Telegram bot or product runtime.

- Split: `development`
- Run label: `development-smoke-20-dev-v3`
- Cases: 20
- Clean / corrupted: 10 / 10

## Metrics

| Metric | Estimate | Wilson 95% CI | Count |
|---|---:|---:|---:|
| Error recall | 70.00% | 39.68%–89.22% | 7/10 |
| Missed-error rate | 30.00% | 10.78%–60.32% | 3/10 |
| False-alert rate | 0.00% | 0.00%–27.75% | 0/10 |
| Challenge-set precision | 100.00% | 64.57%–100.00% | 7/7 |
| Field-localization accuracy | 71.43% | 35.89%–91.78% | 5/7 |
| Structured-output coverage | 100.00% | 83.89%–100.00% | 20/20 |
| Technical failure rate | 0.00% | 0.00%–16.11% | 0/20 |

## Field breakdown

| Field | Corrupted | Alerted | Correct field | Localized recall | Wilson 95% CI |
|---|---:|---:|---:|---:|---:|
| WBS | 3 | 1 | 1 | 33.33% | 6.15%–79.23% |
| Kaltmiete | 3 | 3 | 2 | 66.67% | 20.77%–93.85% |
| rooms | 2 | 1 | 0 | 0.00% | 0.00%–65.76% |
| address/postal code | 0 | 0 | 0 | n/a | n/a |
| district | 1 | 1 | 1 | 100.00% | 20.65%–100.00% |
| floor | 1 | 1 | 1 | 100.00% | 20.65%–100.00% |
| Warmmiete | 0 | 0 | 0 | n/a | n/a |

## Acceptance gates

These are eval-contract targets. Status is calculated from unrounded estimates.

| Gate | Rule | Estimate | Status |
|---|---:|---:|---:|
| `structured_output_coverage` | >= 99.50% | 100.00% | pass |
| `error_recall` | >= 90.00% | 70.00% | fail |
| `false_alert_rate` | <= 8.00% | 0.00% | pass |
| `challenge_set_precision` | >= 85.00% | 100.00% | pass |
| `field_localization_accuracy` | >= 90.00% | 71.43% | fail |
| `wbs_per_field_recall` | >= 90.00% | 33.33% | fail |
| `rent_kalt_per_field_recall` | >= 90.00% | 66.67% | fail |
| `rooms_per_field_recall` | >= 90.00% | 0.00% | fail |

## Output and failure diagnostics

- Invalid JSON: 0
- Invalid schema: 0
- Technical failures: 0
- False positives: 0
- False negatives: 3
- Wrong field localizations: 2

## Operational measurements

- Case result records: 20
- Completed cases: 20
- Request count (including retries): 20
- Retries: 0
- Token usage: 10820 input, 0 cached input, 489 output, 0 reasoning (n=20/20, complete)
- Total recorded cost: $0.010316 (n=20/20, complete)
- Cost per completed case: $0.000516
- Latency `synchronous_case`: p50 900.64 ms, p95 1908.68 ms (n=20/20, complete)

## Diagnostic artifacts

- `false_positives.jsonl`
- `false_negatives.jsonl`
- `field_breakdown.json`
