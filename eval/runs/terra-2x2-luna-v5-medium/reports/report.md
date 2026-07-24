# Synthetic offline AI QA evaluation

Engineering evaluation artifact. Results apply only to this synthetic challenge set and are not production precision or user-impact evidence.
This offline scorer does not integrate OpenAI or AI QA into the Telegram bot or product runtime.

- Split: `terra_prompt_reasoning_screen`
- Run label: `luna-v5-medium`
- Cases: 48
- Clean / corrupted: 16 / 32

## Metrics

| Metric | Estimate | Wilson 95% CI | Count |
|---|---:|---:|---:|
| Error recall | 90.62% | 75.78%–96.76% | 29/32 |
| Missed-error rate | 9.38% | 3.24%–24.22% | 3/32 |
| False-alert rate | 0.00% | 0.00%–19.36% | 0/16 |
| Challenge-set precision | 100.00% | 88.30%–100.00% | 29/29 |
| Field-localization accuracy | 100.00% | 88.30%–100.00% | 29/29 |
| Structured-output coverage | 100.00% | 92.59%–100.00% | 48/48 |
| Technical failure rate | 0.00% | 0.00%–7.41% | 0/48 |

## Field breakdown

| Field | Corrupted | Alerted | Correct field | Localized recall | Wilson 95% CI |
|---|---:|---:|---:|---:|---:|
| WBS | 20 | 18 | 18 | 90.00% | 69.90%–97.21% |
| Kaltmiete | 2 | 2 | 2 | 100.00% | 34.24%–100.00% |
| rooms | 2 | 2 | 2 | 100.00% | 34.24%–100.00% |
| address/postal code | 2 | 2 | 2 | 100.00% | 34.24%–100.00% |
| district | 2 | 1 | 1 | 50.00% | 9.45%–90.55% |
| floor | 2 | 2 | 2 | 100.00% | 34.24%–100.00% |
| Warmmiete | 2 | 2 | 2 | 100.00% | 34.24%–100.00% |

## Acceptance gates

These are eval-contract targets. Status is calculated from unrounded estimates.

| Gate | Rule | Estimate | Status |
|---|---:|---:|---:|
| `structured_output_coverage` | >= 99.50% | 100.00% | pass |
| `error_recall` | >= 90.00% | 90.62% | pass |
| `false_alert_rate` | <= 8.00% | 0.00% | pass |
| `challenge_set_precision` | >= 85.00% | 100.00% | pass |
| `field_localization_accuracy` | >= 90.00% | 100.00% | pass |
| `wbs_per_field_recall` | >= 90.00% | 90.00% | pass |
| `rent_kalt_per_field_recall` | >= 90.00% | 100.00% | pass |
| `rooms_per_field_recall` | >= 90.00% | 100.00% | pass |

## Output and failure diagnostics

- Invalid JSON: 0
- Invalid schema: 0
- Technical failures: 0
- False positives: 0
- False negatives: 3
- Wrong field localizations: 0

## Operational measurements

- Case result records: 48
- Completed cases: 48
- Request count (including retries): 48
- Retries: 0
- Token usage: 58410 input, 0 cached input, 1694 output, 576 reasoning (n=48/48, complete)
- Total recorded cost: $0.171435 (n=48/48, complete)
- Cost per completed case: $0.003572
- Latency `synchronous_case`: p50 1247.07 ms, p95 2975.32 ms (n=48/48, complete)

## Diagnostic artifacts

- `false_positives.jsonl`
- `false_negatives.jsonl`
- `field_breakdown.json`
