# Synthetic offline AI QA evaluation

Engineering evaluation artifact. Results apply only to this synthetic challenge set and are not production precision or user-impact evidence.
This offline scorer does not integrate OpenAI or AI QA into the Telegram bot or product runtime.

- Split: `terra_calibration`
- Run label: `terra-v1-medium-calibration`
- Cases: 280
- Clean / corrupted: 140 / 140

## Metrics

| Metric | Estimate | Wilson 95% CI | Count |
|---|---:|---:|---:|
| Error recall | 95.71% | 90.97%–98.02% | 134/140 |
| Missed-error rate | 4.29% | 1.98%–9.03% | 6/140 |
| False-alert rate | 0.00% | 0.00%–2.67% | 0/140 |
| Challenge-set precision | 100.00% | 97.21%–100.00% | 134/134 |
| Field-localization accuracy | 100.00% | 97.21%–100.00% | 134/134 |
| Structured-output coverage | 100.00% | 98.65%–100.00% | 280/280 |
| Technical failure rate | 0.00% | 0.00%–1.35% | 0/280 |

## Field breakdown

| Field | Corrupted | Alerted | Correct field | Localized recall | Wilson 95% CI |
|---|---:|---:|---:|---:|---:|
| WBS | 56 | 53 | 53 | 94.64% | 85.39%–98.16% |
| Kaltmiete | 21 | 21 | 21 | 100.00% | 84.54%–100.00% |
| rooms | 21 | 19 | 19 | 90.48% | 71.09%–97.35% |
| address/postal code | 14 | 14 | 14 | 100.00% | 78.47%–100.00% |
| district | 10 | 9 | 9 | 90.00% | 59.58%–98.21% |
| floor | 10 | 10 | 10 | 100.00% | 72.25%–100.00% |
| Warmmiete | 8 | 8 | 8 | 100.00% | 67.56%–100.00% |

## Acceptance gates

These are eval-contract targets. Status is calculated from unrounded estimates.

| Gate | Rule | Estimate | Status |
|---|---:|---:|---:|
| `structured_output_coverage` | >= 99.50% | 100.00% | pass |
| `error_recall` | >= 90.00% | 95.71% | pass |
| `false_alert_rate` | <= 8.00% | 0.00% | pass |
| `challenge_set_precision` | >= 85.00% | 100.00% | pass |
| `field_localization_accuracy` | >= 90.00% | 100.00% | pass |
| `wbs_per_field_recall` | >= 90.00% | 94.64% | pass |
| `rent_kalt_per_field_recall` | >= 90.00% | 100.00% | pass |
| `rooms_per_field_recall` | >= 90.00% | 90.48% | pass |

## Output and failure diagnostics

- Invalid JSON: 0
- Invalid schema: 0
- Technical failures: 0
- False positives: 0
- False negatives: 6
- Wrong field localizations: 0

## Operational measurements

- Case result records: 280
- Completed cases: 280
- Request count (including retries): 280
- Retries: 0
- Token usage: 385885 input, 0 cached input, 11634 output, 5019 reasoning (n=280/280, complete)
- Total recorded cost: $1.139223 (n=280/280, complete)
- Cost per completed case: $0.004069
- Latency `synchronous_case`: p50 1141.37 ms, p95 2678.16 ms (n=280/280, complete)

## Diagnostic artifacts

- `false_positives.jsonl`
- `false_negatives.jsonl`
- `field_breakdown.json`
