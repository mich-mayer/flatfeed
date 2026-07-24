# Synthetic offline AI QA evaluation

Engineering evaluation artifact. Results apply only to this synthetic challenge set and are not production precision or user-impact evidence.
This offline scorer does not integrate OpenAI or AI QA into the Telegram bot or product runtime.

- Split: `terra_effort_screen`
- Run label: `terra-effort-screen-low`
- Cases: 48
- Clean / corrupted: 16 / 32

## Metrics

| Metric | Estimate | Wilson 95% CI | Count |
|---|---:|---:|---:|
| Error recall | 84.38% | 68.25%–93.14% | 27/32 |
| Missed-error rate | 15.62% | 6.86%–31.75% | 5/32 |
| False-alert rate | 0.00% | 0.00%–19.36% | 0/16 |
| Challenge-set precision | 100.00% | 87.54%–100.00% | 27/27 |
| Field-localization accuracy | 100.00% | 87.54%–100.00% | 27/27 |
| Structured-output coverage | 100.00% | 92.59%–100.00% | 48/48 |
| Technical failure rate | 0.00% | 0.00%–7.41% | 0/48 |

## Field breakdown

| Field | Corrupted | Alerted | Correct field | Localized recall | Wilson 95% CI |
|---|---:|---:|---:|---:|---:|
| WBS | 20 | 17 | 17 | 85.00% | 63.96%–94.76% |
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
| `error_recall` | >= 90.00% | 84.38% | fail |
| `false_alert_rate` | <= 8.00% | 0.00% | pass |
| `challenge_set_precision` | >= 85.00% | 100.00% | pass |
| `field_localization_accuracy` | >= 90.00% | 100.00% | pass |
| `wbs_per_field_recall` | >= 90.00% | 85.00% | fail |
| `rent_kalt_per_field_recall` | >= 90.00% | 100.00% | pass |
| `rooms_per_field_recall` | >= 90.00% | 100.00% | pass |

## Output and failure diagnostics

- Invalid JSON: 0
- Invalid schema: 0
- Technical failures: 0
- False positives: 0
- False negatives: 5
- Wrong field localizations: 0

## Operational measurements

- Case result records: 48
- Completed cases: 48
- Request count (including retries): 48
- Retries: 0
- Token usage: 58405 input, 0 cached input, 1761 output, 642 reasoning (n=48/48, complete)
- Total recorded cost: $0.172428 (n=48/48, complete)
- Cost per completed case: $0.003592
- Latency `synchronous_case`: p50 1261.27 ms, p95 2831.90 ms (n=48/48, complete)

## Diagnostic artifacts

- `false_positives.jsonl`
- `false_negatives.jsonl`
- `field_breakdown.json`
