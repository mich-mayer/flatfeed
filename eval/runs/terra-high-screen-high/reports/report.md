# Synthetic offline AI QA evaluation

Engineering evaluation artifact. Results apply only to this synthetic challenge set and are not production precision or user-impact evidence.
This offline scorer does not integrate OpenAI or AI QA into the Telegram bot or product runtime.

- Split: `terra_high_reasoning_screen`
- Run label: `terra-v1-high`
- Cases: 48
- Clean / corrupted: 12 / 36

## Metrics

| Metric | Estimate | Wilson 95% CI | Count |
|---|---:|---:|---:|
| Error recall | 100.00% | 90.36%–100.00% | 36/36 |
| Missed-error rate | 0.00% | 0.00%–9.64% | 0/36 |
| False-alert rate | 0.00% | 0.00%–24.25% | 0/12 |
| Challenge-set precision | 100.00% | 90.36%–100.00% | 36/36 |
| Field-localization accuracy | 100.00% | 90.36%–100.00% | 36/36 |
| Structured-output coverage | 100.00% | 92.59%–100.00% | 48/48 |
| Technical failure rate | 0.00% | 0.00%–7.41% | 0/48 |

## Field breakdown

| Field | Corrupted | Alerted | Correct field | Localized recall | Wilson 95% CI |
|---|---:|---:|---:|---:|---:|
| WBS | 14 | 14 | 14 | 100.00% | 78.47%–100.00% |
| Kaltmiete | 2 | 2 | 2 | 100.00% | 34.24%–100.00% |
| rooms | 14 | 14 | 14 | 100.00% | 78.47%–100.00% |
| address/postal code | 2 | 2 | 2 | 100.00% | 34.24%–100.00% |
| district | 2 | 2 | 2 | 100.00% | 34.24%–100.00% |
| floor | 1 | 1 | 1 | 100.00% | 20.65%–100.00% |
| Warmmiete | 1 | 1 | 1 | 100.00% | 20.65%–100.00% |

## Acceptance gates

These are eval-contract targets. Status is calculated from unrounded estimates.

| Gate | Rule | Estimate | Status |
|---|---:|---:|---:|
| `structured_output_coverage` | >= 99.50% | 100.00% | pass |
| `error_recall` | >= 90.00% | 100.00% | pass |
| `false_alert_rate` | <= 8.00% | 0.00% | pass |
| `challenge_set_precision` | >= 85.00% | 100.00% | pass |
| `field_localization_accuracy` | >= 90.00% | 100.00% | pass |
| `wbs_per_field_recall` | >= 90.00% | 100.00% | pass |
| `rent_kalt_per_field_recall` | >= 90.00% | 100.00% | pass |
| `rooms_per_field_recall` | >= 90.00% | 100.00% | pass |

## Output and failure diagnostics

- Invalid JSON: 0
- Invalid schema: 0
- Technical failures: 0
- False positives: 0
- False negatives: 0
- Wrong field localizations: 0

## Operational measurements

- Case result records: 48
- Completed cases: 48
- Request count (including retries): 48
- Retries: 0
- Token usage: 66163 input, 54315 cached input, 2947 output, 1773 reasoning (n=48/48, complete)
- Total recorded cost: $0.087404 (n=48/48, complete)
- Cost per completed case: $0.001821
- Latency `synchronous_case`: p50 1283.42 ms, p95 3206.34 ms (n=48/48, complete)

## Diagnostic artifacts

- `false_positives.jsonl`
- `false_negatives.jsonl`
- `field_breakdown.json`
