# Synthetic offline AI QA evaluation

Engineering evaluation artifact. Results apply only to this synthetic challenge set and are not production precision or user-impact evidence.
This offline scorer does not integrate OpenAI or AI QA into the Telegram bot or product runtime.

- Split: `luna_calibration`
- Run label: `luna-v1-calibration`
- Cases: 100
- Clean / corrupted: 50 / 50

## Metrics

| Metric | Estimate | Wilson 95% CI | Count |
|---|---:|---:|---:|
| Error recall | 96.00% | 86.54%–98.90% | 48/50 |
| Missed-error rate | 4.00% | 1.10%–13.46% | 2/50 |
| False-alert rate | 2.00% | 0.35%–10.50% | 1/50 |
| Challenge-set precision | 97.96% | 89.31%–99.64% | 48/49 |
| Field-localization accuracy | 97.92% | 89.10%–99.63% | 47/48 |
| Structured-output coverage | 100.00% | 96.30%–100.00% | 100/100 |
| Technical failure rate | 0.00% | 0.00%–3.70% | 0/100 |

## Field breakdown

| Field | Corrupted | Alerted | Correct field | Localized recall | Wilson 95% CI |
|---|---:|---:|---:|---:|---:|
| WBS | 13 | 11 | 11 | 84.62% | 57.77%–95.67% |
| Kaltmiete | 10 | 10 | 10 | 100.00% | 72.25%–100.00% |
| rooms | 8 | 8 | 8 | 100.00% | 67.56%–100.00% |
| address/postal code | 7 | 7 | 7 | 100.00% | 64.57%–100.00% |
| district | 5 | 5 | 5 | 100.00% | 56.55%–100.00% |
| floor | 4 | 4 | 3 | 75.00% | 30.06%–95.44% |
| Warmmiete | 3 | 3 | 3 | 100.00% | 43.85%–100.00% |

## Acceptance gates

These are eval-contract targets. Status is calculated from unrounded estimates.

| Gate | Rule | Estimate | Status |
|---|---:|---:|---:|
| `structured_output_coverage` | >= 99.50% | 100.00% | pass |
| `error_recall` | >= 90.00% | 96.00% | pass |
| `false_alert_rate` | <= 8.00% | 2.00% | pass |
| `challenge_set_precision` | >= 85.00% | 97.96% | pass |
| `field_localization_accuracy` | >= 90.00% | 97.92% | pass |
| `wbs_per_field_recall` | >= 90.00% | 84.62% | fail |
| `rent_kalt_per_field_recall` | >= 90.00% | 100.00% | pass |
| `rooms_per_field_recall` | >= 90.00% | 100.00% | pass |

## Output and failure diagnostics

- Invalid JSON: 0
- Invalid schema: 0
- Technical failures: 0
- False positives: 1
- False negatives: 2
- Wrong field localizations: 1

## Operational measurements

- Case result records: 100
- Completed cases: 100
- Request count (including retries): 100
- Retries: 0
- Token usage: 78683 input, 0 cached input, 2260 output, 0 reasoning (n=100/100, complete)
- Total recorded cost: $0.092243 (n=100/100, complete)
- Cost per completed case: $0.000922
- Latency `synchronous_case`: p50 995.50 ms, p95 4511.55 ms (n=100/100, complete)

## Diagnostic artifacts

- `false_positives.jsonl`
- `false_negatives.jsonl`
- `field_breakdown.json`
