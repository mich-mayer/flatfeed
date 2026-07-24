# Synthetic offline AI QA evaluation

Engineering evaluation artifact. Results apply only to this synthetic challenge set and are not production precision or user-impact evidence.
This offline scorer does not integrate OpenAI or AI QA into the Telegram bot or product runtime.

- Split: `luna_validation`
- Run label: `luna-v2-validation`
- Cases: 100
- Clean / corrupted: 50 / 50

## Metrics

| Metric | Estimate | Wilson 95% CI | Count |
|---|---:|---:|---:|
| Error recall | 100.00% | 92.87%–100.00% | 50/50 |
| Missed-error rate | 0.00% | 0.00%–7.13% | 0/50 |
| False-alert rate | 8.00% | 3.15%–18.84% | 4/50 |
| Challenge-set precision | 92.59% | 82.45%–97.08% | 50/54 |
| Field-localization accuracy | 94.00% | 83.78%–97.94% | 47/50 |
| Structured-output coverage | 100.00% | 96.30%–100.00% | 100/100 |
| Technical failure rate | 0.00% | 0.00%–3.70% | 0/100 |

## Field breakdown

| Field | Corrupted | Alerted | Correct field | Localized recall | Wilson 95% CI |
|---|---:|---:|---:|---:|---:|
| WBS | 13 | 13 | 13 | 100.00% | 77.19%–100.00% |
| Kaltmiete | 10 | 10 | 8 | 80.00% | 49.02%–94.33% |
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
| `error_recall` | >= 90.00% | 100.00% | pass |
| `false_alert_rate` | <= 8.00% | 8.00% | pass |
| `challenge_set_precision` | >= 85.00% | 92.59% | pass |
| `field_localization_accuracy` | >= 90.00% | 94.00% | pass |
| `wbs_per_field_recall` | >= 90.00% | 100.00% | pass |
| `rent_kalt_per_field_recall` | >= 90.00% | 80.00% | fail |
| `rooms_per_field_recall` | >= 90.00% | 100.00% | pass |

## Output and failure diagnostics

- Invalid JSON: 0
- Invalid schema: 0
- Technical failures: 0
- False positives: 4
- False negatives: 0
- Wrong field localizations: 3

## Operational measurements

- Case result records: 100
- Completed cases: 100
- Request count (including retries): 100
- Retries: 0
- Token usage: 87143 input, 0 cached input, 2264 output, 0 reasoning (n=100/100, complete)
- Total recorded cost: $0.100727 (n=100/100, complete)
- Cost per completed case: $0.001007
- Latency `synchronous_case`: p50 919.53 ms, p95 2459.99 ms (n=100/100, complete)

## Diagnostic artifacts

- `false_positives.jsonl`
- `false_negatives.jsonl`
- `field_breakdown.json`
