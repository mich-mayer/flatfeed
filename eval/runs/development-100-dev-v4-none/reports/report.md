# Synthetic offline AI QA evaluation

Engineering evaluation artifact. Results apply only to this synthetic challenge set and are not production precision or user-impact evidence.
This offline scorer does not integrate OpenAI or AI QA into the Telegram bot or product runtime.

- Split: `development`
- Run label: `development-100-dev-v4-none`
- Cases: 100
- Clean / corrupted: 50 / 50

## Metrics

| Metric | Estimate | Wilson 95% CI | Count |
|---|---:|---:|---:|
| Error recall | 70.00% | 56.25%–80.90% | 35/50 |
| Missed-error rate | 30.00% | 19.10%–43.75% | 15/50 |
| False-alert rate | 0.00% | 0.00%–7.13% | 0/50 |
| Challenge-set precision | 100.00% | 90.11%–100.00% | 35/35 |
| Field-localization accuracy | 97.14% | 85.47%–99.49% | 34/35 |
| Structured-output coverage | 100.00% | 96.30%–100.00% | 100/100 |
| Technical failure rate | 0.00% | 0.00%–3.70% | 0/100 |

## Field breakdown

| Field | Corrupted | Alerted | Correct field | Localized recall | Wilson 95% CI |
|---|---:|---:|---:|---:|---:|
| WBS | 13 | 6 | 6 | 46.15% | 23.21%–70.86% |
| Kaltmiete | 10 | 8 | 8 | 80.00% | 49.02%–94.33% |
| rooms | 8 | 6 | 5 | 62.50% | 30.57%–86.32% |
| address/postal code | 7 | 6 | 6 | 85.71% | 48.69%–97.43% |
| district | 5 | 5 | 5 | 100.00% | 56.55%–100.00% |
| floor | 4 | 3 | 3 | 75.00% | 30.06%–95.44% |
| Warmmiete | 3 | 1 | 1 | 33.33% | 6.15%–79.23% |

## Acceptance gates

These are eval-contract targets. Status is calculated from unrounded estimates.

| Gate | Rule | Estimate | Status |
|---|---:|---:|---:|
| `structured_output_coverage` | >= 99.50% | 100.00% | pass |
| `error_recall` | >= 90.00% | 70.00% | fail |
| `false_alert_rate` | <= 8.00% | 0.00% | pass |
| `challenge_set_precision` | >= 85.00% | 100.00% | pass |
| `field_localization_accuracy` | >= 90.00% | 97.14% | pass |
| `wbs_per_field_recall` | >= 90.00% | 46.15% | fail |
| `rent_kalt_per_field_recall` | >= 90.00% | 80.00% | fail |
| `rooms_per_field_recall` | >= 90.00% | 62.50% | fail |

## Output and failure diagnostics

- Invalid JSON: 0
- Invalid schema: 0
- Technical failures: 0
- False positives: 0
- False negatives: 15
- Wrong field localizations: 1

## Operational measurements

- Case result records: 100
- Completed cases: 100
- Request count (including retries): 100
- Retries: 0
- Token usage: 68515 input, 0 cached input, 2255 output, 0 reasoning (n=100/100, complete)
- Total recorded cost: $0.061534 (n=100/100, complete)
- Cost per completed case: $0.000615
- Latency `synchronous_case`: p50 834.67 ms, p95 3276.13 ms (n=100/100, complete)

## Diagnostic artifacts

- `false_positives.jsonl`
- `false_negatives.jsonl`
- `field_breakdown.json`
