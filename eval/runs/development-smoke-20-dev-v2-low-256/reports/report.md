# Synthetic offline AI QA evaluation

Engineering evaluation artifact. Results apply only to this synthetic challenge set and are not production precision or user-impact evidence.
This offline scorer does not integrate OpenAI or AI QA into the Telegram bot or product runtime.

- Split: `development`
- Run label: `development-smoke-20-dev-v2-low-256`
- Cases: 20
- Clean / corrupted: 10 / 10

## Metrics

| Metric | Estimate | Wilson 95% CI | Count |
|---|---:|---:|---:|
| Error recall | 90.00% | 59.58%–98.21% | 9/10 |
| Missed-error rate | 10.00% | 1.79%–40.42% | 1/10 |
| False-alert rate | 20.00% | 5.67%–50.98% | 2/10 |
| Challenge-set precision | 81.82% | 52.30%–94.86% | 9/11 |
| Field-localization accuracy | 77.78% | 45.26%–93.68% | 7/9 |
| Structured-output coverage | 100.00% | 83.89%–100.00% | 20/20 |
| Technical failure rate | 0.00% | 0.00%–16.11% | 0/20 |

## Field breakdown

| Field | Corrupted | Alerted | Correct field | Localized recall | Wilson 95% CI |
|---|---:|---:|---:|---:|---:|
| WBS | 3 | 2 | 2 | 66.67% | 20.77%–93.85% |
| Kaltmiete | 3 | 3 | 2 | 66.67% | 20.77%–93.85% |
| rooms | 2 | 2 | 1 | 50.00% | 9.45%–90.55% |
| address/postal code | 0 | 0 | 0 | n/a | n/a |
| district | 1 | 1 | 1 | 100.00% | 20.65%–100.00% |
| floor | 1 | 1 | 1 | 100.00% | 20.65%–100.00% |
| Warmmiete | 0 | 0 | 0 | n/a | n/a |

## Acceptance gates

These are eval-contract targets. Status is calculated from unrounded estimates.

| Gate | Rule | Estimate | Status |
|---|---:|---:|---:|
| `structured_output_coverage` | >= 99.50% | 100.00% | pass |
| `error_recall` | >= 90.00% | 90.00% | pass |
| `false_alert_rate` | <= 8.00% | 20.00% | fail |
| `challenge_set_precision` | >= 85.00% | 81.82% | fail |
| `field_localization_accuracy` | >= 90.00% | 77.78% | fail |
| `wbs_per_field_recall` | >= 90.00% | 66.67% | fail |
| `rent_kalt_per_field_recall` | >= 90.00% | 66.67% | fail |
| `rooms_per_field_recall` | >= 90.00% | 50.00% | fail |

## Output and failure diagnostics

- Invalid JSON: 0
- Invalid schema: 0
- Technical failures: 0
- False positives: 2
- False negatives: 1
- Wrong field localizations: 2

## Operational measurements

- Case result records: 20
- Completed cases: 20
- Request count (including retries): 20
- Retries: 0
- Token usage: 11300 input, 0 cached input, 2437 output, 1947 reasoning (n=20/20, complete)
- Total recorded cost: $0.019442 (n=20/20, complete)
- Cost per completed case: $0.000972
- Latency `synchronous_case`: p50 1581.35 ms, p95 3405.68 ms (n=20/20, complete)

## Diagnostic artifacts

- `false_positives.jsonl`
- `false_negatives.jsonl`
- `field_breakdown.json`
