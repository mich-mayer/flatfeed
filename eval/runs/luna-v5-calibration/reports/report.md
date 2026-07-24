# Synthetic offline AI QA evaluation

Engineering evaluation artifact. Results apply only to this synthetic challenge set and are not production precision or user-impact evidence.
This offline scorer does not integrate OpenAI or AI QA into the Telegram bot or product runtime.

- Split: `luna_v5_calibration`
- Run label: `luna-v5-calibration`
- Cases: 280
- Clean / corrupted: 140 / 140

## Metrics

| Metric | Estimate | Wilson 95% CI | Count |
|---|---:|---:|---:|
| Error recall | 90.71% | 84.76%–94.49% | 127/140 |
| Missed-error rate | 9.29% | 5.51%–15.24% | 13/140 |
| False-alert rate | 3.57% | 1.53%–8.09% | 5/140 |
| Challenge-set precision | 96.21% | 91.44%–98.37% | 127/132 |
| Field-localization accuracy | 96.85% | 92.18%–98.77% | 123/127 |
| Structured-output coverage | 100.00% | 98.65%–100.00% | 280/280 |
| Technical failure rate | 0.00% | 0.00%–1.35% | 0/280 |

## Field breakdown

| Field | Corrupted | Alerted | Correct field | Localized recall | Wilson 95% CI |
|---|---:|---:|---:|---:|---:|
| WBS | 56 | 45 | 45 | 80.36% | 68.16%–88.66% |
| Kaltmiete | 21 | 21 | 20 | 95.24% | 77.33%–99.15% |
| rooms | 21 | 21 | 21 | 100.00% | 84.54%–100.00% |
| address/postal code | 14 | 13 | 12 | 85.71% | 60.06%–95.99% |
| district | 10 | 10 | 8 | 80.00% | 49.02%–94.33% |
| floor | 10 | 10 | 10 | 100.00% | 72.25%–100.00% |
| Warmmiete | 8 | 7 | 7 | 87.50% | 52.91%–97.76% |

## Acceptance gates

These are eval-contract targets. Status is calculated from unrounded estimates.

| Gate | Rule | Estimate | Status |
|---|---:|---:|---:|
| `structured_output_coverage` | >= 99.50% | 100.00% | pass |
| `error_recall` | >= 90.00% | 90.71% | pass |
| `false_alert_rate` | <= 8.00% | 3.57% | pass |
| `challenge_set_precision` | >= 85.00% | 96.21% | pass |
| `field_localization_accuracy` | >= 90.00% | 96.85% | pass |
| `wbs_per_field_recall` | >= 90.00% | 80.36% | fail |
| `rent_kalt_per_field_recall` | >= 90.00% | 95.24% | pass |
| `rooms_per_field_recall` | >= 90.00% | 100.00% | pass |

## Output and failure diagnostics

- Invalid JSON: 0
- Invalid schema: 0
- Technical failures: 0
- False positives: 5
- False negatives: 13
- Wrong field localizations: 4

## Operational measurements

- Case result records: 280
- Completed cases: 280
- Request count (including retries): 280
- Retries: 0
- Token usage: 341084 input, 0 cached input, 6305 output, 0 reasoning (n=280/280, complete)
- Total recorded cost: $0.378914 (n=280/280, complete)
- Cost per completed case: $0.001353
- Latency `synchronous_case`: p50 1025.56 ms, p95 2889.62 ms (n=280/280, complete)

## Diagnostic artifacts

- `false_positives.jsonl`
- `false_negatives.jsonl`
- `field_breakdown.json`
