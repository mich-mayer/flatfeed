# Synthetic offline AI QA evaluation

Engineering evaluation artifact. Results apply only to this synthetic challenge set and are not production precision or user-impact evidence.
This offline scorer does not integrate OpenAI or AI QA into the Telegram bot or product runtime.

- Split: `luna_v3_calibration`
- Run label: `luna-v3-final-calibration`
- Cases: 200
- Clean / corrupted: 100 / 100

## Metrics

| Metric | Estimate | Wilson 95% CI | Count |
|---|---:|---:|---:|
| Error recall | 99.00% | 94.55%–99.82% | 99/100 |
| Missed-error rate | 1.00% | 0.18%–5.45% | 1/100 |
| False-alert rate | 5.00% | 2.15%–11.18% | 5/100 |
| Challenge-set precision | 95.19% | 89.24%–97.93% | 99/104 |
| Field-localization accuracy | 97.98% | 92.93%–99.44% | 97/99 |
| Structured-output coverage | 100.00% | 98.12%–100.00% | 200/200 |
| Technical failure rate | 0.00% | 0.00%–1.88% | 0/200 |

## Field breakdown

| Field | Corrupted | Alerted | Correct field | Localized recall | Wilson 95% CI |
|---|---:|---:|---:|---:|---:|
| WBS | 20 | 20 | 20 | 100.00% | 83.89%–100.00% |
| Kaltmiete | 25 | 25 | 23 | 92.00% | 75.03%–97.78% |
| rooms | 15 | 15 | 15 | 100.00% | 79.61%–100.00% |
| address/postal code | 10 | 10 | 10 | 100.00% | 72.25%–100.00% |
| district | 8 | 7 | 7 | 87.50% | 52.91%–97.76% |
| floor | 15 | 15 | 15 | 100.00% | 79.61%–100.00% |
| Warmmiete | 7 | 7 | 7 | 100.00% | 64.57%–100.00% |

## Acceptance gates

These are eval-contract targets. Status is calculated from unrounded estimates.

| Gate | Rule | Estimate | Status |
|---|---:|---:|---:|
| `structured_output_coverage` | >= 99.50% | 100.00% | pass |
| `error_recall` | >= 90.00% | 99.00% | pass |
| `false_alert_rate` | <= 8.00% | 5.00% | pass |
| `challenge_set_precision` | >= 85.00% | 95.19% | pass |
| `field_localization_accuracy` | >= 90.00% | 97.98% | pass |
| `wbs_per_field_recall` | >= 90.00% | 100.00% | pass |
| `rent_kalt_per_field_recall` | >= 90.00% | 92.00% | pass |
| `rooms_per_field_recall` | >= 90.00% | 100.00% | pass |

## Output and failure diagnostics

- Invalid JSON: 0
- Invalid schema: 0
- Technical failures: 0
- False positives: 5
- False negatives: 1
- Wrong field localizations: 2

## Operational measurements

- Case result records: 200
- Completed cases: 200
- Request count (including retries): 200
- Retries: 0
- Token usage: 199450 input, 0 cached input, 4519 output, 0 reasoning (n=200/200, complete)
- Total recorded cost: $0.226564 (n=200/200, complete)
- Cost per completed case: $0.001133
- Latency `synchronous_case`: p50 963.04 ms, p95 4637.83 ms (n=200/200, complete)

## Diagnostic artifacts

- `false_positives.jsonl`
- `false_negatives.jsonl`
- `field_breakdown.json`
