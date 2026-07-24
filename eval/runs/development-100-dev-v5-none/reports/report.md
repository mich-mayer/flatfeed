# Synthetic offline AI QA evaluation

Engineering evaluation artifact. Results apply only to this synthetic challenge set and are not production precision or user-impact evidence.
This offline scorer does not integrate OpenAI or AI QA into the Telegram bot or product runtime.

- Split: `development`
- Run label: `development-100-dev-v5-none`
- Cases: 100
- Clean / corrupted: 50 / 50

## Metrics

| Metric | Estimate | Wilson 95% CI | Count |
|---|---:|---:|---:|
| Error recall | 70.00% | 56.25%–80.90% | 35/50 |
| Missed-error rate | 30.00% | 19.10%–43.75% | 15/50 |
| False-alert rate | 10.00% | 4.35%–21.36% | 5/50 |
| Challenge-set precision | 87.50% | 73.89%–94.54% | 35/40 |
| Field-localization accuracy | 91.43% | 77.62%–97.04% | 32/35 |
| Structured-output coverage | 100.00% | 96.30%–100.00% | 100/100 |
| Technical failure rate | 0.00% | 0.00%–3.70% | 0/100 |

## Field breakdown

| Field | Corrupted | Alerted | Correct field | Localized recall | Wilson 95% CI |
|---|---:|---:|---:|---:|---:|
| WBS | 13 | 6 | 6 | 46.15% | 23.21%–70.86% |
| Kaltmiete | 10 | 7 | 7 | 70.00% | 39.68%–89.22% |
| rooms | 8 | 7 | 6 | 75.00% | 40.93%–92.85% |
| address/postal code | 7 | 6 | 5 | 71.43% | 35.89%–91.78% |
| district | 5 | 4 | 3 | 60.00% | 23.07%–88.24% |
| floor | 4 | 3 | 3 | 75.00% | 30.06%–95.44% |
| Warmmiete | 3 | 2 | 2 | 66.67% | 20.77%–93.85% |

## Acceptance gates

These are eval-contract targets. Status is calculated from unrounded estimates.

| Gate | Rule | Estimate | Status |
|---|---:|---:|---:|
| `structured_output_coverage` | >= 99.50% | 100.00% | pass |
| `error_recall` | >= 90.00% | 70.00% | fail |
| `false_alert_rate` | <= 8.00% | 10.00% | fail |
| `challenge_set_precision` | >= 85.00% | 87.50% | pass |
| `field_localization_accuracy` | >= 90.00% | 91.43% | pass |
| `wbs_per_field_recall` | >= 90.00% | 46.15% | fail |
| `rent_kalt_per_field_recall` | >= 90.00% | 70.00% | fail |
| `rooms_per_field_recall` | >= 90.00% | 75.00% | fail |

## Output and failure diagnostics

- Invalid JSON: 0
- Invalid schema: 0
- Technical failures: 0
- False positives: 5
- False negatives: 15
- Wrong field localizations: 3

## Operational measurements

- Case result records: 100
- Completed cases: 100
- Request count (including retries): 100
- Retries: 0
- Token usage: 60015 input, 0 cached input, 2265 output, 0 reasoning (n=100/100, complete)
- Total recorded cost: $0.055204 (n=100/100, complete)
- Cost per completed case: $0.000552
- Latency `synchronous_case`: p50 789.96 ms, p95 1577.28 ms (n=100/100, complete)

## Diagnostic artifacts

- `false_positives.jsonl`
- `false_negatives.jsonl`
- `field_breakdown.json`
