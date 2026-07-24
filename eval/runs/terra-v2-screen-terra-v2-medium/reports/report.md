# Synthetic offline AI QA evaluation

Engineering evaluation artifact. Results apply only to this synthetic challenge set and are not production precision or user-impact evidence.
This offline scorer does not integrate OpenAI or AI QA into the Telegram bot or product runtime.

- Split: `terra_v2_prompt_screen`
- Run label: `terra-v2-medium`
- Cases: 64
- Clean / corrupted: 16 / 48

## Metrics

| Metric | Estimate | Wilson 95% CI | Count |
|---|---:|---:|---:|
| Error recall | 89.58% | 77.83%–95.47% | 43/48 |
| Missed-error rate | 10.42% | 4.53%–22.17% | 5/48 |
| False-alert rate | 0.00% | 0.00%–19.36% | 0/16 |
| Challenge-set precision | 100.00% | 91.80%–100.00% | 43/43 |
| Field-localization accuracy | 100.00% | 91.80%–100.00% | 43/43 |
| Structured-output coverage | 100.00% | 94.34%–100.00% | 64/64 |
| Technical failure rate | 0.00% | 0.00%–5.66% | 0/64 |

## Field breakdown

| Field | Corrupted | Alerted | Correct field | Localized recall | Wilson 95% CI |
|---|---:|---:|---:|---:|---:|
| WBS | 20 | 17 | 17 | 85.00% | 63.96%–94.76% |
| Kaltmiete | 2 | 2 | 2 | 100.00% | 34.24%–100.00% |
| rooms | 20 | 20 | 20 | 100.00% | 83.89%–100.00% |
| address/postal code | 2 | 1 | 1 | 50.00% | 9.45%–90.55% |
| district | 2 | 1 | 1 | 50.00% | 9.45%–90.55% |
| floor | 1 | 1 | 1 | 100.00% | 20.65%–100.00% |
| Warmmiete | 1 | 1 | 1 | 100.00% | 20.65%–100.00% |

## Acceptance gates

These are eval-contract targets. Status is calculated from unrounded estimates.

| Gate | Rule | Estimate | Status |
|---|---:|---:|---:|
| `structured_output_coverage` | >= 99.50% | 100.00% | pass |
| `error_recall` | >= 90.00% | 89.58% | fail |
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

- Case result records: 64
- Completed cases: 64
- Request count (including retries): 64
- Retries: 0
- Token usage: 100716 input, 85583 cached input, 2608 output, 1108 reasoning (n=64/64, complete)
- Total recorded cost: $0.098348 (n=64/64, complete)
- Cost per completed case: $0.001537
- Latency `synchronous_case`: p50 1107.66 ms, p95 3077.97 ms (n=64/64, complete)

## Diagnostic artifacts

- `false_positives.jsonl`
- `false_negatives.jsonl`
- `field_breakdown.json`
