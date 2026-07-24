# Synthetic offline AI QA evaluation

Engineering evaluation artifact. Results apply only to this synthetic challenge set and are not production precision or user-impact evidence.
This offline scorer does not integrate OpenAI or AI QA into the Telegram bot or product runtime.

- Split: `terra_high_validation`
- Run label: `terra-v1-high-validation`
- Cases: 280
- Clean / corrupted: 140 / 140

## Metrics

| Metric | Estimate | Wilson 95% CI | Count |
|---|---:|---:|---:|
| Error recall | 99.29% | 96.07%–99.87% | 139/140 |
| Missed-error rate | 0.71% | 0.13%–3.93% | 1/140 |
| False-alert rate | 0.71% | 0.13%–3.93% | 1/140 |
| Challenge-set precision | 99.29% | 96.07%–99.87% | 139/140 |
| Field-localization accuracy | 100.00% | 97.31%–100.00% | 139/139 |
| Structured-output coverage | 100.00% | 98.65%–100.00% | 280/280 |
| Technical failure rate | 0.00% | 0.00%–1.35% | 0/280 |

## Field breakdown

| Field | Corrupted | Alerted | Correct field | Localized recall | Wilson 95% CI |
|---|---:|---:|---:|---:|---:|
| WBS | 56 | 56 | 56 | 100.00% | 93.58%–100.00% |
| Kaltmiete | 21 | 21 | 21 | 100.00% | 84.54%–100.00% |
| rooms | 21 | 20 | 20 | 95.24% | 77.33%–99.15% |
| address/postal code | 14 | 14 | 14 | 100.00% | 78.47%–100.00% |
| district | 10 | 10 | 10 | 100.00% | 72.25%–100.00% |
| floor | 10 | 10 | 10 | 100.00% | 72.25%–100.00% |
| Warmmiete | 8 | 8 | 8 | 100.00% | 67.56%–100.00% |

## Acceptance gates

These are eval-contract targets. Status is calculated from unrounded estimates.

| Gate | Rule | Estimate | Status |
|---|---:|---:|---:|
| `structured_output_coverage` | >= 99.50% | 100.00% | pass |
| `error_recall` | >= 90.00% | 99.29% | pass |
| `false_alert_rate` | <= 8.00% | 0.71% | pass |
| `challenge_set_precision` | >= 85.00% | 99.29% | pass |
| `field_localization_accuracy` | >= 90.00% | 100.00% | pass |
| `wbs_per_field_recall` | >= 90.00% | 100.00% | pass |
| `rent_kalt_per_field_recall` | >= 90.00% | 100.00% | pass |
| `rooms_per_field_recall` | >= 90.00% | 95.24% | pass |

## Output and failure diagnostics

- Invalid JSON: 0
- Invalid schema: 0
- Technical failures: 0
- False positives: 1
- False negatives: 1
- Wrong field localizations: 0

## Operational measurements

- Case result records: 280
- Completed cases: 280
- Request count (including retries): 280
- Retries: 0
- Token usage: 385850 input, 322269 cached input, 16787 output, 9942 reasoning (n=280/280, complete)
- Total recorded cost: $0.491325 (n=280/280, complete)
- Cost per completed case: $0.001755
- Latency `synchronous_case`: p50 1235.34 ms, p95 3547.31 ms (n=280/280, complete)

## Diagnostic artifacts

- `false_positives.jsonl`
- `false_negatives.jsonl`
- `field_breakdown.json`
