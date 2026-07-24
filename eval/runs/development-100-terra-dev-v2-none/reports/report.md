# Synthetic offline AI QA evaluation

Engineering evaluation artifact. Results apply only to this synthetic challenge set and are not production precision or user-impact evidence.
This offline scorer does not integrate OpenAI or AI QA into the Telegram bot or product runtime.

- Split: `development`
- Run label: `development-100-terra-dev-v2-none`
- Cases: 100
- Clean / corrupted: 50 / 50

## Metrics

| Metric | Estimate | Wilson 95% CI | Count |
|---|---:|---:|---:|
| Error recall | 98.00% | 89.50%–99.65% | 49/50 |
| Missed-error rate | 2.00% | 0.35%–10.50% | 1/50 |
| False-alert rate | 42.00% | 29.38%–55.77% | 21/50 |
| Challenge-set precision | 70.00% | 58.46%–79.46% | 49/70 |
| Field-localization accuracy | 83.67% | 70.96%–91.49% | 41/49 |
| Structured-output coverage | 100.00% | 96.30%–100.00% | 100/100 |
| Technical failure rate | 0.00% | 0.00%–3.70% | 0/100 |

## Field breakdown

| Field | Corrupted | Alerted | Correct field | Localized recall | Wilson 95% CI |
|---|---:|---:|---:|---:|---:|
| WBS | 13 | 13 | 13 | 100.00% | 77.19%–100.00% |
| Kaltmiete | 10 | 10 | 9 | 90.00% | 59.58%–98.21% |
| rooms | 8 | 8 | 7 | 87.50% | 52.91%–97.76% |
| address/postal code | 7 | 7 | 4 | 57.14% | 25.05%–84.18% |
| district | 5 | 4 | 1 | 20.00% | 3.62%–62.45% |
| floor | 4 | 4 | 4 | 100.00% | 51.01%–100.00% |
| Warmmiete | 3 | 3 | 3 | 100.00% | 43.85%–100.00% |

## Acceptance gates

These are eval-contract targets. Status is calculated from unrounded estimates.

| Gate | Rule | Estimate | Status |
|---|---:|---:|---:|
| `structured_output_coverage` | >= 99.50% | 100.00% | pass |
| `error_recall` | >= 90.00% | 98.00% | pass |
| `false_alert_rate` | <= 8.00% | 42.00% | fail |
| `challenge_set_precision` | >= 85.00% | 70.00% | fail |
| `field_localization_accuracy` | >= 90.00% | 83.67% | fail |
| `wbs_per_field_recall` | >= 90.00% | 100.00% | pass |
| `rent_kalt_per_field_recall` | >= 90.00% | 90.00% | pass |
| `rooms_per_field_recall` | >= 90.00% | 87.50% | fail |

## Output and failure diagnostics

- Invalid JSON: 0
- Invalid schema: 0
- Technical failures: 0
- False positives: 21
- False negatives: 1
- Wrong field localizations: 8

## Operational measurements

- Case result records: 100
- Completed cases: 100
- Request count (including retries): 100
- Retries: 0
- Token usage: 56315 input, 0 cached input, 2278 output, 0 reasoning (n=100/100, complete)
- Total recorded cost: $0.174957 (n=100/100, complete)
- Cost per completed case: $0.001750
- Latency `synchronous_case`: p50 974.66 ms, p95 2269.76 ms (n=100/100, complete)

## Diagnostic artifacts

- `false_positives.jsonl`
- `false_negatives.jsonl`
- `field_breakdown.json`
