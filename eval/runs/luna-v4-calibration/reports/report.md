# Synthetic offline AI QA evaluation

Engineering evaluation artifact. Results apply only to this synthetic challenge set and are not production precision or user-impact evidence.
This offline scorer does not integrate OpenAI or AI QA into the Telegram bot or product runtime.

- Split: `luna_v4_calibration`
- Run label: `luna-v4-calibration`
- Cases: 240
- Clean / corrupted: 120 / 120

## Metrics

| Metric | Estimate | Wilson 95% CI | Count |
|---|---:|---:|---:|
| Error recall | 97.50% | 92.91%–99.15% | 117/120 |
| Missed-error rate | 2.50% | 0.85%–7.09% | 3/120 |
| False-alert rate | 15.83% | 10.38%–23.41% | 19/120 |
| Challenge-set precision | 86.03% | 79.21%–90.87% | 117/136 |
| Field-localization accuracy | 88.89% | 81.91%–93.39% | 104/117 |
| Structured-output coverage | 100.00% | 98.42%–100.00% | 240/240 |
| Technical failure rate | 0.00% | 0.00%–1.58% | 0/240 |

## Field breakdown

| Field | Corrupted | Alerted | Correct field | Localized recall | Wilson 95% CI |
|---|---:|---:|---:|---:|---:|
| WBS | 50 | 48 | 48 | 96.00% | 86.54%–98.90% |
| Kaltmiete | 20 | 20 | 16 | 80.00% | 58.40%–91.93% |
| rooms | 15 | 14 | 12 | 80.00% | 54.81%–92.95% |
| address/postal code | 10 | 10 | 10 | 100.00% | 72.25%–100.00% |
| district | 10 | 10 | 7 | 70.00% | 39.68%–89.22% |
| floor | 8 | 8 | 6 | 75.00% | 40.93%–92.85% |
| Warmmiete | 7 | 7 | 5 | 71.43% | 35.89%–91.78% |

## Acceptance gates

These are eval-contract targets. Status is calculated from unrounded estimates.

| Gate | Rule | Estimate | Status |
|---|---:|---:|---:|
| `structured_output_coverage` | >= 99.50% | 100.00% | pass |
| `error_recall` | >= 90.00% | 97.50% | pass |
| `false_alert_rate` | <= 8.00% | 15.83% | fail |
| `challenge_set_precision` | >= 85.00% | 86.03% | pass |
| `field_localization_accuracy` | >= 90.00% | 88.89% | fail |
| `wbs_per_field_recall` | >= 90.00% | 96.00% | pass |
| `rent_kalt_per_field_recall` | >= 90.00% | 80.00% | fail |
| `rooms_per_field_recall` | >= 90.00% | 80.00% | fail |

## Output and failure diagnostics

- Invalid JSON: 0
- Invalid schema: 0
- Technical failures: 0
- False positives: 19
- False negatives: 3
- Wrong field localizations: 13

## Operational measurements

- Case result records: 240
- Completed cases: 240
- Request count (including retries): 240
- Retries: 0
- Token usage: 287967 input, 0 cached input, 5434 output, 0 reasoning (n=240/240, complete)
- Total recorded cost: $0.320571 (n=240/240, complete)
- Cost per completed case: $0.001336
- Latency `synchronous_case`: p50 1030.17 ms, p95 3015.18 ms (n=240/240, complete)

## Diagnostic artifacts

- `false_positives.jsonl`
- `false_negatives.jsonl`
- `field_breakdown.json`
