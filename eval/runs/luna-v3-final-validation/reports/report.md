# Synthetic offline AI QA evaluation

Engineering evaluation artifact. Results apply only to this synthetic challenge set and are not production precision or user-impact evidence.
This offline scorer does not integrate OpenAI or AI QA into the Telegram bot or product runtime.

- Split: `luna_v3_validation`
- Run label: `luna-v3-final-validation`
- Cases: 200
- Clean / corrupted: 100 / 100

## Metrics

| Metric | Estimate | Wilson 95% CI | Count |
|---|---:|---:|---:|
| Error recall | 95.00% | 88.82%–97.85% | 95/100 |
| Missed-error rate | 5.00% | 2.15%–11.18% | 5/100 |
| False-alert rate | 3.00% | 1.03%–8.45% | 3/100 |
| Challenge-set precision | 96.94% | 91.38%–98.95% | 95/98 |
| Field-localization accuracy | 98.95% | 94.28%–99.81% | 94/95 |
| Structured-output coverage | 100.00% | 98.12%–100.00% | 200/200 |
| Technical failure rate | 0.00% | 0.00%–1.88% | 0/200 |

## Field breakdown

| Field | Corrupted | Alerted | Correct field | Localized recall | Wilson 95% CI |
|---|---:|---:|---:|---:|---:|
| WBS | 20 | 17 | 17 | 85.00% | 63.96%–94.76% |
| Kaltmiete | 25 | 25 | 25 | 100.00% | 86.68%–100.00% |
| rooms | 15 | 15 | 15 | 100.00% | 79.61%–100.00% |
| address/postal code | 10 | 8 | 8 | 80.00% | 49.02%–94.33% |
| district | 8 | 8 | 7 | 87.50% | 52.91%–97.76% |
| floor | 15 | 15 | 15 | 100.00% | 79.61%–100.00% |
| Warmmiete | 7 | 7 | 7 | 100.00% | 64.57%–100.00% |

## Acceptance gates

These are eval-contract targets. Status is calculated from unrounded estimates.

| Gate | Rule | Estimate | Status |
|---|---:|---:|---:|
| `structured_output_coverage` | >= 99.50% | 100.00% | pass |
| `error_recall` | >= 90.00% | 95.00% | pass |
| `false_alert_rate` | <= 8.00% | 3.00% | pass |
| `challenge_set_precision` | >= 85.00% | 96.94% | pass |
| `field_localization_accuracy` | >= 90.00% | 98.95% | pass |
| `wbs_per_field_recall` | >= 90.00% | 85.00% | fail |
| `rent_kalt_per_field_recall` | >= 90.00% | 100.00% | pass |
| `rooms_per_field_recall` | >= 90.00% | 100.00% | pass |

## Output and failure diagnostics

- Invalid JSON: 0
- Invalid schema: 0
- Technical failures: 0
- False positives: 3
- False negatives: 5
- Wrong field localizations: 1

## Operational measurements

- Case result records: 200
- Completed cases: 200
- Request count (including retries): 200
- Retries: 0
- Token usage: 199484 input, 0 cached input, 4509 output, 0 reasoning (n=200/200, complete)
- Total recorded cost: $0.226538 (n=200/200, complete)
- Cost per completed case: $0.001133
- Latency `synchronous_case`: p50 908.74 ms, p95 8364.26 ms (n=200/200, complete)

## Diagnostic artifacts

- `false_positives.jsonl`
- `false_negatives.jsonl`
- `field_breakdown.json`
