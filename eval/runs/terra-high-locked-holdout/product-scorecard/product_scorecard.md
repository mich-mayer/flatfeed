# AI QA Product Scorecard

**Evidence:** Synthetic locked holdout

Synthetic offline parser-QA evidence only; not live-source, production-prevalence, or renter-outcome evidence.

- Model: `gpt-5.6-terra` with `reasoning_effort=high`
- Prompt: `terra-v1`
- Cases: 600 (300 clean, 300 corrupted)
- Final-test decision: `fail`

## Four simple metrics

| Metric | Result | Target | Count | Status |
|---|---:|---:|---:|---:|
| Parser Error Detection Rate | 97.0% | >= 95.0% | 291/300 | pass |
| False Alert Rate | 0.0% | <= 3.0% | 0/300 | pass |
| Correct Field Detection Rate | 97.0% | >= 90.0% | 291/300 | pass |
| Successful Check Rate | 100.0% | >= 99.5% | 600/600 | pass |

## Checked fields

| Field | Correct field | Role | Guardrail |
|---|---:|---|---:|
| WBS | 100.0% (75/75) | matching-critical | >= 90.0% (pass) |
| district | 100.0% (30/30) | matching-critical | >= 90.0% (pass) |
| Kaltmiete | 100.0% (60/60) | matching-critical | >= 90.0% (pass) |
| rooms | 86.0% (43/50) | matching-critical | >= 90.0% (fail) |
| address/postal code | 95.0% (38/40) | diagnostic | n/a |
| floor | 100.0% (25/25) | diagnostic | n/a |
| Warmmiete | 100.0% (20/20) | diagnostic | n/a |

## Real-world boundary

- This scorecard measures a synthetic challenge set, not performance on live housing-provider listings or real parser-error prevalence.
- A real product would need human review of every AI alert and an independent random sample of listings that received no alert so missed parser errors can be measured.
- FlatFeed does not currently use housing-provider data without permission, so that real-world audit workflow is planned rather than implemented in this prototype.
- The checker can evaluate only listings and raw text that the collection layer obtained; missing listings require a separate source-coverage control.
