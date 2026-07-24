# Synthetic offline AI QA evaluation

Engineering evaluation artifact. Results apply only to this synthetic challenge set and are not production precision or user-impact evidence.
This offline scorer does not integrate OpenAI or AI QA into the Telegram bot or product runtime.

- Split: `terra_effort_screen`
- Run label: `terra-effort-screen-none`
- Cases: 48
- Clean / corrupted: 16 / 32

## Metrics

| Metric | Estimate | Wilson 95% CI | Count |
|---|---:|---:|---:|
| Error recall | 81.25% | 64.69%–91.11% | 26/32 |
| Missed-error rate | 18.75% | 8.89%–35.31% | 6/32 |
| False-alert rate | 0.00% | 0.00%–19.36% | 0/16 |
| Challenge-set precision | 100.00% | 87.13%–100.00% | 26/26 |
| Field-localization accuracy | 100.00% | 87.13%–100.00% | 26/26 |
| Structured-output coverage | 100.00% | 92.59%–100.00% | 48/48 |
| Technical failure rate | 0.00% | 0.00%–7.41% | 0/48 |

## Field breakdown

| Field | Corrupted | Alerted | Correct field | Localized recall | Wilson 95% CI |
|---|---:|---:|---:|---:|---:|
| WBS | 20 | 16 | 16 | 80.00% | 58.40%–91.93% |
| Kaltmiete | 2 | 2 | 2 | 100.00% | 34.24%–100.00% |
| rooms | 2 | 2 | 2 | 100.00% | 34.24%–100.00% |
| address/postal code | 2 | 0 | 0 | 0.00% | 0.00%–65.76% |
| district | 2 | 2 | 2 | 100.00% | 34.24%–100.00% |
| floor | 2 | 2 | 2 | 100.00% | 34.24%–100.00% |
| Warmmiete | 2 | 2 | 2 | 100.00% | 34.24%–100.00% |

## Acceptance gates

These are eval-contract targets. Status is calculated from unrounded estimates.

| Gate | Rule | Estimate | Status |
|---|---:|---:|---:|
| `structured_output_coverage` | >= 99.50% | 100.00% | pass |
| `error_recall` | >= 90.00% | 81.25% | fail |
| `false_alert_rate` | <= 8.00% | 0.00% | pass |
| `challenge_set_precision` | >= 85.00% | 100.00% | pass |
| `field_localization_accuracy` | >= 90.00% | 100.00% | pass |
| `wbs_per_field_recall` | >= 90.00% | 80.00% | fail |
| `rent_kalt_per_field_recall` | >= 90.00% | 100.00% | pass |
| `rooms_per_field_recall` | >= 90.00% | 100.00% | pass |

## Output and failure diagnostics

- Invalid JSON: 0
- Invalid schema: 0
- Technical failures: 0
- False positives: 0
- False negatives: 6
- Wrong field localizations: 0

## Operational measurements

- Case result records: 48
- Completed cases: 48
- Request count (including retries): 48
- Retries: 0
- Token usage: 58405 input, 0 cached input, 1080 output, 0 reasoning (n=48/48, complete)
- Total recorded cost: $0.162213 (n=48/48, complete)
- Cost per completed case: $0.003379
- Latency `synchronous_case`: p50 1079.67 ms, p95 2408.91 ms (n=48/48, complete)

## Diagnostic artifacts

- `false_positives.jsonl`
- `false_negatives.jsonl`
- `field_breakdown.json`
