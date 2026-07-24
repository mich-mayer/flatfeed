# Synthetic offline AI QA evaluation

Engineering evaluation artifact. Results apply only to this synthetic challenge set and are not production precision or user-impact evidence.
This offline scorer does not integrate OpenAI or AI QA into the Telegram bot or product runtime.

- Split: `terra_prompt_reasoning_screen`
- Run label: `luna-v5-low`
- Cases: 48
- Clean / corrupted: 16 / 32

## Metrics

| Metric | Estimate | Wilson 95% CI | Count |
|---|---:|---:|---:|
| Error recall | 87.50% | 71.93%–95.03% | 28/32 |
| Missed-error rate | 12.50% | 4.97%–28.07% | 4/32 |
| False-alert rate | 0.00% | 0.00%–19.36% | 0/16 |
| Challenge-set precision | 100.00% | 87.94%–100.00% | 28/28 |
| Field-localization accuracy | 100.00% | 87.94%–100.00% | 28/28 |
| Structured-output coverage | 97.92% | 89.10%–99.63% | 47/48 |
| Technical failure rate | 2.08% | 0.37%–10.90% | 1/48 |

## Field breakdown

| Field | Corrupted | Alerted | Correct field | Localized recall | Wilson 95% CI |
|---|---:|---:|---:|---:|---:|
| WBS | 20 | 17 | 17 | 85.00% | 63.96%–94.76% |
| Kaltmiete | 2 | 2 | 2 | 100.00% | 34.24%–100.00% |
| rooms | 2 | 2 | 2 | 100.00% | 34.24%–100.00% |
| address/postal code | 2 | 2 | 2 | 100.00% | 34.24%–100.00% |
| district | 2 | 2 | 2 | 100.00% | 34.24%–100.00% |
| floor | 2 | 2 | 2 | 100.00% | 34.24%–100.00% |
| Warmmiete | 2 | 1 | 1 | 50.00% | 9.45%–90.55% |

## Acceptance gates

These are eval-contract targets. Status is calculated from unrounded estimates.

| Gate | Rule | Estimate | Status |
|---|---:|---:|---:|
| `structured_output_coverage` | >= 99.50% | 97.92% | fail |
| `error_recall` | >= 90.00% | 87.50% | fail |
| `false_alert_rate` | <= 8.00% | 0.00% | pass |
| `challenge_set_precision` | >= 85.00% | 100.00% | pass |
| `field_localization_accuracy` | >= 90.00% | 100.00% | pass |
| `wbs_per_field_recall` | >= 90.00% | 85.00% | fail |
| `rent_kalt_per_field_recall` | >= 90.00% | 100.00% | pass |
| `rooms_per_field_recall` | >= 90.00% | 100.00% | pass |

## Output and failure diagnostics

- Invalid JSON: 0
- Invalid schema: 0
- Technical failures: 1
- False positives: 0
- False negatives: 4
- Wrong field localizations: 0

## Operational measurements

- Case result records: 48
- Completed cases: 47
- Request count (including retries): 48
- Retries: 0
- Token usage: 57187 input, 0 cached input, 1910 output, 803 reasoning (n=47/48, partial)
- Total recorded cost: $0.171618 (n=47/48, partial)
- Cost per completed case: n/a
- Latency `synchronous_case`: p50 1289.14 ms, p95 2143.93 ms (n=48/48, complete)

## Diagnostic artifacts

- `false_positives.jsonl`
- `false_negatives.jsonl`
- `field_breakdown.json`
