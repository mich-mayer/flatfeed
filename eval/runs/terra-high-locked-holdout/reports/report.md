# Synthetic offline AI QA evaluation

Engineering evaluation artifact. Results apply only to this synthetic challenge set and are not production precision or user-impact evidence.
This offline scorer does not integrate OpenAI or AI QA into the Telegram bot or product runtime.

- Split: `locked_holdout`
- Run label: `terra-v1-high-locked-holdout`
- Cases: 600
- Clean / corrupted: 300 / 300

## Metrics

| Metric | Estimate | Wilson 95% CI | Count |
|---|---:|---:|---:|
| Error recall | 97.00% | 94.40%–98.41% | 291/300 |
| Missed-error rate | 3.00% | 1.59%–5.60% | 9/300 |
| False-alert rate | 0.00% | 0.00%–1.26% | 0/300 |
| Challenge-set precision | 100.00% | 98.70%–100.00% | 291/291 |
| Field-localization accuracy | 100.00% | 98.70%–100.00% | 291/291 |
| Structured-output coverage | 100.00% | 99.36%–100.00% | 600/600 |
| Technical failure rate | 0.00% | 0.00%–0.64% | 0/600 |

## Field breakdown

| Field | Corrupted | Alerted | Correct field | Localized recall | Wilson 95% CI |
|---|---:|---:|---:|---:|---:|
| WBS | 75 | 75 | 75 | 100.00% | 95.13%–100.00% |
| Kaltmiete | 60 | 60 | 60 | 100.00% | 93.98%–100.00% |
| rooms | 50 | 43 | 43 | 86.00% | 73.81%–93.05% |
| address/postal code | 40 | 38 | 38 | 95.00% | 83.50%–98.62% |
| district | 30 | 30 | 30 | 100.00% | 88.65%–100.00% |
| floor | 25 | 25 | 25 | 100.00% | 86.68%–100.00% |
| Warmmiete | 20 | 20 | 20 | 100.00% | 83.89%–100.00% |

## Acceptance gates

These are eval-contract targets. Status is calculated from unrounded estimates.

| Gate | Rule | Estimate | Status |
|---|---:|---:|---:|
| `structured_output_coverage` | >= 99.50% | 100.00% | pass |
| `error_recall` | >= 90.00% | 97.00% | pass |
| `false_alert_rate` | <= 8.00% | 0.00% | pass |
| `challenge_set_precision` | >= 85.00% | 100.00% | pass |
| `field_localization_accuracy` | >= 90.00% | 100.00% | pass |
| `wbs_per_field_recall` | >= 90.00% | 100.00% | pass |
| `rent_kalt_per_field_recall` | >= 90.00% | 100.00% | pass |
| `rooms_per_field_recall` | >= 90.00% | 86.00% | fail |

## Output and failure diagnostics

- Invalid JSON: 0
- Invalid schema: 0
- Technical failures: 0
- False positives: 0
- False negatives: 9
- Wrong field localizations: 0

## Operational measurements

- Case result records: 600
- Completed cases: 600
- Request count (including retries): 600
- Retries: 0
- Token usage: 825139 input, 697646 cached input, 34544 output, 19847 reasoning (n=600/600, complete)
- Total recorded cost: $1.011304 (n=600/600, complete)
- Cost per completed case: $0.001686
- Latency `synchronous_case`: p50 1279.68 ms, p95 3549.98 ms (n=600/600, complete)

## Diagnostic artifacts

- `false_positives.jsonl`
- `false_negatives.jsonl`
- `field_breakdown.json`
