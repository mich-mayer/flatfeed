# Synthetic offline AI QA evaluation

Engineering evaluation artifact. Results apply only to this synthetic challenge set and are not production precision or user-impact evidence.
This offline scorer does not integrate OpenAI or AI QA into the Telegram bot or product runtime.

- Split: `development`
- Run label: `development-smoke-20-dev-v2-low`
- Cases: 20
- Clean / corrupted: 10 / 10

## Metrics

| Metric | Estimate | Wilson 95% CI | Count |
|---|---:|---:|---:|
| Error recall | 30.00% | 10.78%–60.32% | 3/10 |
| Missed-error rate | 70.00% | 39.68%–89.22% | 7/10 |
| False-alert rate | 0.00% | 0.00%–27.75% | 0/10 |
| Challenge-set precision | 100.00% | 43.85%–100.00% | 3/3 |
| Field-localization accuracy | 100.00% | 43.85%–100.00% | 3/3 |
| Structured-output coverage | 25.00% | 11.19%–46.87% | 5/20 |
| Technical failure rate | 75.00% | 53.13%–88.81% | 15/20 |

## Field breakdown

| Field | Corrupted | Alerted | Correct field | Localized recall | Wilson 95% CI |
|---|---:|---:|---:|---:|---:|
| WBS | 3 | 2 | 2 | 66.67% | 20.77%–93.85% |
| Kaltmiete | 3 | 0 | 0 | 0.00% | 0.00%–56.15% |
| rooms | 2 | 1 | 1 | 50.00% | 9.45%–90.55% |
| address/postal code | 0 | 0 | 0 | n/a | n/a |
| district | 1 | 0 | 0 | 0.00% | 0.00%–79.35% |
| floor | 1 | 0 | 0 | 0.00% | 0.00%–79.35% |
| Warmmiete | 0 | 0 | 0 | n/a | n/a |

## Acceptance gates

These are eval-contract targets. Status is calculated from unrounded estimates.

| Gate | Rule | Estimate | Status |
|---|---:|---:|---:|
| `structured_output_coverage` | >= 99.50% | 25.00% | fail |
| `error_recall` | >= 90.00% | 30.00% | fail |
| `false_alert_rate` | <= 8.00% | 0.00% | pass |
| `challenge_set_precision` | >= 85.00% | 100.00% | pass |
| `field_localization_accuracy` | >= 90.00% | 100.00% | pass |
| `wbs_per_field_recall` | >= 90.00% | 66.67% | fail |
| `rent_kalt_per_field_recall` | >= 90.00% | 0.00% | fail |
| `rooms_per_field_recall` | >= 90.00% | 50.00% | fail |

## Output and failure diagnostics

- Invalid JSON: 0
- Invalid schema: 0
- Technical failures: 15
- False positives: 0
- False negatives: 7
- Wrong field localizations: 0

## Operational measurements

- Case result records: 20
- Completed cases: 5
- Request count (including retries): 20
- Retries: 0
- Token usage: 2773 input, 0 cached input, 261 output, 139 reasoning (n=5/20, partial)
- Total recorded cost: $0.003254 (n=5/20, partial)
- Cost per completed case: n/a
- Latency `synchronous_case`: p50 1048.33 ms, p95 2795.01 ms (n=20/20, complete)

## Diagnostic artifacts

- `false_positives.jsonl`
- `false_negatives.jsonl`
- `field_breakdown.json`
