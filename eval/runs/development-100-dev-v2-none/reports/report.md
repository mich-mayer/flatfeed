# Synthetic offline AI QA evaluation

Engineering evaluation artifact. Results apply only to this synthetic challenge set and are not production precision or user-impact evidence.
This offline scorer does not integrate OpenAI or AI QA into the Telegram bot or product runtime.

- Split: `development`
- Run label: `development-100-dev-v2-none`
- Cases: 100
- Clean / corrupted: 50 / 50

## Metrics

| Metric | Estimate | Wilson 95% CI | Count |
|---|---:|---:|---:|
| Error recall | 86.00% | 73.81%–93.05% | 43/50 |
| Missed-error rate | 14.00% | 6.95%–26.19% | 7/50 |
| False-alert rate | 10.00% | 4.35%–21.36% | 5/50 |
| Challenge-set precision | 89.58% | 77.83%–95.47% | 43/48 |
| Field-localization accuracy | 88.37% | 75.52%–94.93% | 38/43 |
| Structured-output coverage | 100.00% | 96.30%–100.00% | 100/100 |
| Technical failure rate | 0.00% | 0.00%–3.70% | 0/100 |

## Field breakdown

| Field | Corrupted | Alerted | Correct field | Localized recall | Wilson 95% CI |
|---|---:|---:|---:|---:|---:|
| WBS | 13 | 10 | 10 | 76.92% | 49.74%–91.82% |
| Kaltmiete | 10 | 10 | 10 | 100.00% | 72.25%–100.00% |
| rooms | 8 | 7 | 5 | 62.50% | 30.57%–86.32% |
| address/postal code | 7 | 5 | 3 | 42.86% | 15.82%–74.95% |
| district | 5 | 5 | 4 | 80.00% | 37.55%–96.38% |
| floor | 4 | 3 | 3 | 75.00% | 30.06%–95.44% |
| Warmmiete | 3 | 3 | 3 | 100.00% | 43.85%–100.00% |

## Acceptance gates

These are eval-contract targets. Status is calculated from unrounded estimates.

| Gate | Rule | Estimate | Status |
|---|---:|---:|---:|
| `structured_output_coverage` | >= 99.50% | 100.00% | pass |
| `error_recall` | >= 90.00% | 86.00% | fail |
| `false_alert_rate` | <= 8.00% | 10.00% | fail |
| `challenge_set_precision` | >= 85.00% | 89.58% | pass |
| `field_localization_accuracy` | >= 90.00% | 88.37% | fail |
| `wbs_per_field_recall` | >= 90.00% | 76.92% | fail |
| `rent_kalt_per_field_recall` | >= 90.00% | 100.00% | pass |
| `rooms_per_field_recall` | >= 90.00% | 62.50% | fail |

## Output and failure diagnostics

- Invalid JSON: 0
- Invalid schema: 0
- Technical failures: 0
- False positives: 5
- False negatives: 7
- Wrong field localizations: 5

## Operational measurements

- Case result records: 100
- Completed cases: 100
- Request count (including retries): 100
- Retries: 0
- Token usage: 56315 input, 0 cached input, 2267 output, 0 reasoning (n=100/100, complete)
- Total recorded cost: $0.052438 (n=100/100, complete)
- Cost per completed case: $0.000524
- Latency `synchronous_case`: p50 876.29 ms, p95 2741.62 ms (n=100/100, complete)

## Diagnostic artifacts

- `false_positives.jsonl`
- `false_negatives.jsonl`
- `field_breakdown.json`
