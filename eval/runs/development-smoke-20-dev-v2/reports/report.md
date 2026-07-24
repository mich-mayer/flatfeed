# Synthetic offline AI QA evaluation

Engineering evaluation artifact. Results apply only to this synthetic challenge set and are not production precision or user-impact evidence.
This offline scorer does not integrate OpenAI or AI QA into the Telegram bot or product runtime.

- Split: `development`
- Run label: `development-smoke-20-dev-v2`
- Cases: 20
- Clean / corrupted: 10 / 10

## Metrics

| Metric | Estimate | Wilson 95% CI | Count |
|---|---:|---:|---:|
| Error recall | 90.00% | 59.58%–98.21% | 9/10 |
| Missed-error rate | 10.00% | 1.79%–40.42% | 1/10 |
| False-alert rate | 0.00% | 0.00%–27.75% | 0/10 |
| Challenge-set precision | 100.00% | 70.09%–100.00% | 9/9 |
| Field-localization accuracy | 77.78% | 45.26%–93.68% | 7/9 |
| Structured-output coverage | 100.00% | 83.89%–100.00% | 20/20 |
| Technical failure rate | 0.00% | 0.00%–16.11% | 0/20 |

## Field breakdown

| Field | Corrupted | Alerted | Correct field | Localized recall | Wilson 95% CI |
|---|---:|---:|---:|---:|---:|
| WBS | 3 | 2 | 2 | 66.67% | 20.77%–93.85% |
| Kaltmiete | 3 | 3 | 2 | 66.67% | 20.77%–93.85% |
| rooms | 2 | 2 | 1 | 50.00% | 9.45%–90.55% |
| address/postal code | 0 | 0 | 0 | n/a | n/a |
| district | 1 | 1 | 1 | 100.00% | 20.65%–100.00% |
| floor | 1 | 1 | 1 | 100.00% | 20.65%–100.00% |
| Warmmiete | 0 | 0 | 0 | n/a | n/a |

## Acceptance gates

These are eval-contract targets. Status is calculated from unrounded estimates.

| Gate | Rule | Estimate | Status |
|---|---:|---:|---:|
| `structured_output_coverage` | >= 99.50% | 100.00% | pass |
| `error_recall` | >= 90.00% | 90.00% | pass |
| `false_alert_rate` | <= 8.00% | 0.00% | pass |
| `challenge_set_precision` | >= 85.00% | 100.00% | pass |
| `field_localization_accuracy` | >= 90.00% | 77.78% | fail |
| `wbs_per_field_recall` | >= 90.00% | 66.67% | fail |
| `rent_kalt_per_field_recall` | >= 90.00% | 66.67% | fail |
| `rooms_per_field_recall` | >= 90.00% | 50.00% | fail |

## Output and failure diagnostics

- Invalid JSON: 0
- Invalid schema: 0
- Technical failures: 0
- False positives: 0
- False negatives: 1
- Wrong field localizations: 2

## Operational measurements

- Case result records: 20
- Completed cases: 20
- Request count (including retries): 20
- Retries: 0
- Token usage: 11300 input, 0 cached input, 454 output, 0 reasoning (n=20/20, complete)
- Total recorded cost: $0.010518 (n=20/20, complete)
- Cost per completed case: $0.000526
- Latency `synchronous_case`: p50 807.96 ms, p95 2667.95 ms (n=20/20, complete)

## Diagnostic artifacts

- `false_positives.jsonl`
- `false_negatives.jsonl`
- `field_breakdown.json`
