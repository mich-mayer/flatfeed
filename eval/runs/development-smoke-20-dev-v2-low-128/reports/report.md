# Synthetic offline AI QA evaluation

Engineering evaluation artifact. Results apply only to this synthetic challenge set and are not production precision or user-impact evidence.
This offline scorer does not integrate OpenAI or AI QA into the Telegram bot or product runtime.

- Split: `development`
- Run label: `development-smoke-20-dev-v2-low-128`
- Cases: 20
- Clean / corrupted: 10 / 10

## Metrics

| Metric | Estimate | Wilson 95% CI | Count |
|---|---:|---:|---:|
| Error recall | 50.00% | 23.66%–76.34% | 5/10 |
| Missed-error rate | 50.00% | 23.66%–76.34% | 5/10 |
| False-alert rate | 20.00% | 5.67%–50.98% | 2/10 |
| Challenge-set precision | 71.43% | 35.89%–91.78% | 5/7 |
| Field-localization accuracy | 80.00% | 37.55%–96.38% | 4/5 |
| Structured-output coverage | 65.00% | 43.29%–81.88% | 13/20 |
| Technical failure rate | 35.00% | 18.12%–56.71% | 7/20 |

## Field breakdown

| Field | Corrupted | Alerted | Correct field | Localized recall | Wilson 95% CI |
|---|---:|---:|---:|---:|---:|
| WBS | 3 | 2 | 2 | 66.67% | 20.77%–93.85% |
| Kaltmiete | 3 | 1 | 0 | 0.00% | 0.00%–56.15% |
| rooms | 2 | 1 | 1 | 50.00% | 9.45%–90.55% |
| address/postal code | 0 | 0 | 0 | n/a | n/a |
| district | 1 | 0 | 0 | 0.00% | 0.00%–79.35% |
| floor | 1 | 1 | 1 | 100.00% | 20.65%–100.00% |
| Warmmiete | 0 | 0 | 0 | n/a | n/a |

## Acceptance gates

These are eval-contract targets. Status is calculated from unrounded estimates.

| Gate | Rule | Estimate | Status |
|---|---:|---:|---:|
| `structured_output_coverage` | >= 99.50% | 65.00% | fail |
| `error_recall` | >= 90.00% | 50.00% | fail |
| `false_alert_rate` | <= 8.00% | 20.00% | fail |
| `challenge_set_precision` | >= 85.00% | 71.43% | fail |
| `field_localization_accuracy` | >= 90.00% | 80.00% | fail |
| `wbs_per_field_recall` | >= 90.00% | 66.67% | fail |
| `rent_kalt_per_field_recall` | >= 90.00% | 0.00% | fail |
| `rooms_per_field_recall` | >= 90.00% | 50.00% | fail |

## Output and failure diagnostics

- Invalid JSON: 0
- Invalid schema: 0
- Technical failures: 7
- False positives: 2
- False negatives: 5
- Wrong field localizations: 1

## Operational measurements

- Case result records: 20
- Completed cases: 13
- Request count (including retries): 20
- Retries: 0
- Token usage: 7312 input, 0 cached input, 1050 output, 733 reasoning (n=13/20, partial)
- Total recorded cost: $0.010209 (n=13/20, partial)
- Cost per completed case: n/a
- Latency `synchronous_case`: p50 1574.78 ms, p95 4706.72 ms (n=20/20, complete)

## Diagnostic artifacts

- `false_positives.jsonl`
- `false_negatives.jsonl`
- `field_breakdown.json`
