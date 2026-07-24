# Synthetic offline AI QA evaluation

Engineering evaluation artifact. Results apply only to this synthetic challenge set and are not production precision or user-impact evidence.
This offline scorer does not integrate OpenAI or AI QA into the Telegram bot or product runtime.

- Split: `terra_v2_prompt_screen`
- Run label: `terra-v1-medium`
- Cases: 64
- Clean / corrupted: 16 / 48

## Metrics

| Metric | Estimate | Wilson 95% CI | Count |
|---|---:|---:|---:|
| Error recall | 95.83% | 86.02%–98.85% | 46/48 |
| Missed-error rate | 4.17% | 1.15%–13.98% | 2/48 |
| False-alert rate | 0.00% | 0.00%–19.36% | 0/16 |
| Challenge-set precision | 100.00% | 92.29%–100.00% | 46/46 |
| Field-localization accuracy | 100.00% | 92.29%–100.00% | 46/46 |
| Structured-output coverage | 100.00% | 94.34%–100.00% | 64/64 |
| Technical failure rate | 0.00% | 0.00%–5.66% | 0/64 |

## Field breakdown

| Field | Corrupted | Alerted | Correct field | Localized recall | Wilson 95% CI |
|---|---:|---:|---:|---:|---:|
| WBS | 20 | 19 | 19 | 95.00% | 76.39%–99.11% |
| Kaltmiete | 2 | 2 | 2 | 100.00% | 34.24%–100.00% |
| rooms | 20 | 19 | 19 | 95.00% | 76.39%–99.11% |
| address/postal code | 2 | 2 | 2 | 100.00% | 34.24%–100.00% |
| district | 2 | 2 | 2 | 100.00% | 34.24%–100.00% |
| floor | 1 | 1 | 1 | 100.00% | 20.65%–100.00% |
| Warmmiete | 1 | 1 | 1 | 100.00% | 20.65%–100.00% |

## Acceptance gates

These are eval-contract targets. Status is calculated from unrounded estimates.

| Gate | Rule | Estimate | Status |
|---|---:|---:|---:|
| `structured_output_coverage` | >= 99.50% | 100.00% | pass |
| `error_recall` | >= 90.00% | 95.83% | pass |
| `false_alert_rate` | <= 8.00% | 0.00% | pass |
| `challenge_set_precision` | >= 85.00% | 100.00% | pass |
| `field_localization_accuracy` | >= 90.00% | 100.00% | pass |
| `wbs_per_field_recall` | >= 90.00% | 95.00% | pass |
| `rent_kalt_per_field_recall` | >= 90.00% | 100.00% | pass |
| `rooms_per_field_recall` | >= 90.00% | 95.00% | pass |

## Output and failure diagnostics

- Invalid JSON: 0
- Invalid schema: 0
- Technical failures: 0
- False positives: 0
- False negatives: 2
- Wrong field localizations: 0

## Operational measurements

- Case result records: 64
- Completed cases: 64
- Request count (including retries): 64
- Retries: 0
- Token usage: 88172 input, 74834 cached input, 2806 output, 1291 reasoning (n=64/64, complete)
- Total recorded cost: $0.094144 (n=64/64, complete)
- Cost per completed case: $0.001471
- Latency `synchronous_case`: p50 1070.39 ms, p95 2000.99 ms (n=64/64, complete)

## Diagnostic artifacts

- `false_positives.jsonl`
- `false_negatives.jsonl`
- `field_breakdown.json`
