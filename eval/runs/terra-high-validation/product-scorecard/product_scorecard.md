# AI QA Product Scorecard

**Evidence:** Synthetic frozen validation

Synthetic offline parser-QA evidence only; not live-source, production-prevalence, or renter-outcome evidence.

- Model: `gpt-5.6-terra` with `reasoning_effort=high`
- Prompt: `terra-v1`
- Cases: 280 (140 clean, 140 corrupted)
- Product decision: `pass`

## Four simple metrics

| Metric | Result | Target | Count | Status |
|---|---:|---:|---:|---:|
| Parser Error Detection Rate | 99.3% | >= 95.0% | 139/140 | pass |
| False Alert Rate | 0.7% | <= 3.0% | 1/140 | pass |
| Correct Field Detection Rate | 99.3% | >= 90.0% | 139/140 | pass |
| Successful Check Rate | 100.0% | >= 99.5% | 280/280 | pass |

## Checked fields

| Field | Correct field | Role | Guardrail |
|---|---:|---|---:|
| WBS | 100.0% (56/56) | matching-critical | >= 90.0% (pass) |
| district | 100.0% (10/10) | matching-critical | >= 90.0% (pass) |
| Kaltmiete | 100.0% (21/21) | matching-critical | >= 90.0% (pass) |
| rooms | 95.2% (20/21) | matching-critical | >= 90.0% (pass) |
| address/postal code | 100.0% (14/14) | diagnostic | n/a |
| floor | 100.0% (10/10) | diagnostic | n/a |
| Warmmiete | 100.0% (8/8) | diagnostic | n/a |

## Real-world boundary

- This scorecard measures a synthetic challenge set, not performance on live housing-provider listings or real parser-error prevalence.
- A real product would need human review of every AI alert and an independent random sample of listings that received no alert so missed parser errors can be measured.
- FlatFeed does not currently use housing-provider data without permission, so that real-world audit workflow is planned rather than implemented in this prototype.
- The checker can evaluate only listings and raw text that the collection layer obtained; missing listings require a separate source-coverage control.
