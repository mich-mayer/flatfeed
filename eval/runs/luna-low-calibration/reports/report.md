# Synthetic offline AI QA evaluation

Engineering evaluation artifact. Results apply only to this synthetic challenge set and are not production precision or user-impact evidence.
This offline scorer does not integrate OpenAI or AI QA into the Telegram bot or product runtime.

- Split: `luna_low_calibration`
- Run label: `luna-low-calibration`
- Cases: 280
- Clean / corrupted: 140 / 140

## Metrics

| Metric | Estimate | Wilson 95% CI | Count |
|---|---:|---:|---:|
| Error recall | 94.29% | 89.13%–97.08% | 132/140 |
| Missed-error rate | 5.71% | 2.92%–10.87% | 8/140 |
| False-alert rate | 0.00% | 0.00%–2.67% | 0/140 |
| Challenge-set precision | 100.00% | 97.17%–100.00% | 132/132 |
| Field-localization accuracy | 100.00% | 97.17%–100.00% | 132/132 |
| Structured-output coverage | 100.00% | 98.65%–100.00% | 280/280 |
| Technical failure rate | 0.00% | 0.00%–1.35% | 0/280 |

## Field breakdown

| Field | Corrupted | Alerted | Correct field | Localized recall | Wilson 95% CI |
|---|---:|---:|---:|---:|---:|
| WBS | 56 | 50 | 50 | 89.29% | 78.53%–95.00% |
| Kaltmiete | 21 | 21 | 21 | 100.00% | 84.54%–100.00% |
| rooms | 21 | 21 | 21 | 100.00% | 84.54%–100.00% |
| address/postal code | 14 | 13 | 13 | 92.86% | 68.53%–98.73% |
| district | 10 | 9 | 9 | 90.00% | 59.58%–98.21% |
| floor | 10 | 10 | 10 | 100.00% | 72.25%–100.00% |
| Warmmiete | 8 | 8 | 8 | 100.00% | 67.56%–100.00% |

## Acceptance gates

These are eval-contract targets. Status is calculated from unrounded estimates.

| Gate | Rule | Estimate | Status |
|---|---:|---:|---:|
| `structured_output_coverage` | >= 99.50% | 100.00% | pass |
| `error_recall` | >= 90.00% | 94.29% | pass |
| `false_alert_rate` | <= 8.00% | 0.00% | pass |
| `challenge_set_precision` | >= 85.00% | 100.00% | pass |
| `field_localization_accuracy` | >= 90.00% | 100.00% | pass |
| `wbs_per_field_recall` | >= 90.00% | 89.29% | fail |
| `rent_kalt_per_field_recall` | >= 90.00% | 100.00% | pass |
| `rooms_per_field_recall` | >= 90.00% | 100.00% | pass |

## Output and failure diagnostics

- Invalid JSON: 0
- Invalid schema: 0
- Technical failures: 0
- False positives: 0
- False negatives: 8
- Wrong field localizations: 0

## Operational measurements

- Case result records: 280
- Completed cases: 280
- Request count (including retries): 280
- Retries: 0
- Token usage: 341114 input, 0 cached input, 12345 output, 5740 reasoning (n=280/280, complete)
- Total recorded cost: $0.415184 (n=280/280, complete)
- Cost per completed case: $0.001483
- Latency `synchronous_case`: p50 1171.84 ms, p95 2688.68 ms (n=280/280, complete)

## Diagnostic artifacts

- `false_positives.jsonl`
- `false_negatives.jsonl`
- `field_breakdown.json`
