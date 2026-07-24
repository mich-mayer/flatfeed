# Synthetic offline AI QA evaluation

Engineering evaluation artifact. Results apply only to this synthetic challenge set and are not production precision or user-impact evidence.
This offline scorer does not integrate OpenAI or AI QA into the Telegram bot or product runtime.

- Split: `development`
- Run label: `development-100-luna-dev-v2-none`
- Cases: 100
- Clean / corrupted: 50 / 50

## Metrics

| Metric | Estimate | Wilson 95% CI | Count |
|---|---:|---:|---:|
| Error recall | 96.00% | 86.54%–98.90% | 48/50 |
| Missed-error rate | 4.00% | 1.10%–13.46% | 2/50 |
| False-alert rate | 16.00% | 8.34%–28.51% | 8/50 |
| Challenge-set precision | 85.71% | 74.26%–92.58% | 48/56 |
| Field-localization accuracy | 95.83% | 86.02%–98.85% | 46/48 |
| Structured-output coverage | 100.00% | 96.30%–100.00% | 100/100 |
| Technical failure rate | 0.00% | 0.00%–3.70% | 0/100 |

## Field breakdown

| Field | Corrupted | Alerted | Correct field | Localized recall | Wilson 95% CI |
|---|---:|---:|---:|---:|---:|
| WBS | 13 | 13 | 13 | 100.00% | 77.19%–100.00% |
| Kaltmiete | 10 | 10 | 10 | 100.00% | 72.25%–100.00% |
| rooms | 8 | 8 | 7 | 87.50% | 52.91%–97.76% |
| address/postal code | 7 | 7 | 6 | 85.71% | 48.69%–97.43% |
| district | 5 | 3 | 3 | 60.00% | 23.07%–88.24% |
| floor | 4 | 4 | 4 | 100.00% | 51.01%–100.00% |
| Warmmiete | 3 | 3 | 3 | 100.00% | 43.85%–100.00% |

## Acceptance gates

These are eval-contract targets. Status is calculated from unrounded estimates.

| Gate | Rule | Estimate | Status |
|---|---:|---:|---:|
| `structured_output_coverage` | >= 99.50% | 100.00% | pass |
| `error_recall` | >= 90.00% | 96.00% | pass |
| `false_alert_rate` | <= 8.00% | 16.00% | fail |
| `challenge_set_precision` | >= 85.00% | 85.71% | pass |
| `field_localization_accuracy` | >= 90.00% | 95.83% | pass |
| `wbs_per_field_recall` | >= 90.00% | 100.00% | pass |
| `rent_kalt_per_field_recall` | >= 90.00% | 100.00% | pass |
| `rooms_per_field_recall` | >= 90.00% | 87.50% | fail |

## Output and failure diagnostics

- Invalid JSON: 0
- Invalid schema: 0
- Technical failures: 0
- False positives: 8
- False negatives: 2
- Wrong field localizations: 2

## Operational measurements

- Case result records: 100
- Completed cases: 100
- Request count (including retries): 100
- Retries: 0
- Token usage: 56315 input, 0 cached input, 2267 output, 0 reasoning (n=100/100, complete)
- Total recorded cost: $0.069917 (n=100/100, complete)
- Cost per completed case: $0.000699
- Latency `synchronous_case`: p50 915.10 ms, p95 3913.82 ms (n=100/100, complete)

## Diagnostic artifacts

- `false_positives.jsonl`
- `false_negatives.jsonl`
- `field_breakdown.json`
