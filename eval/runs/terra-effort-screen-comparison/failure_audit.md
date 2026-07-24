# Terra Reasoning-Screen Failure Audit

Aggregate development diagnostics only. No new model call, validation, locked holdout, or Sol run was used.

## Outcome

- Terra-low misses: 5 of 32 corrupted cases.
- Failed fields: address_postal_code, wbs.

## Terra-low outcomes by field

| Field | Cases | Misses | Recall |
|---|---:|---:|---:|
| wbs | 20 | 3 | 85.0% |
| address_postal_code | 2 | 2 | 0.0% |
| rooms | 2 | 0 | 100.0% |
| rent_warm | 2 | 0 | 100.0% |
| rent_kalt | 2 | 0 | 100.0% |
| floor | 2 | 0 | 100.0% |
| district | 2 | 0 | 100.0% |

## Missed corruption subtypes

| Field and subtype | Cases | Misses | Recall |
|---|---:|---:|---:|
| address_postal_code:postal_code_substitution | 2 | 2 | 0.0% |
| wbs:wbs_range_boundary_shift | 11 | 1 | 90.9% |
| wbs:wbs_specificity_confusion | 4 | 1 | 75.0% |
| wbs:wbs_requirement_added | 4 | 1 | 75.0% |

## Paired evidence

- Both correct: 41.
- Low only correct: 2.
- None only correct: 1.
- Both wrong: 4.
- Both postal-code substitutions were missed by both configurations: 2/2.
- Terra-low's 3 WBS misses span 3 corruption subtypes.
- Caution: The screen is a 48-case development diagnostic; subtype counts are not independent performance estimates.

## Prompt assessment

The prompt may contribute: 2/2 postal-code substitutions were missed by both Terra configurations, while low also missed 3 WBS subtypes. However, the audit does not support one narrow Terra-specific prompt change. The failed advancement gates span address/postal-code and WBS, and the WBS misses span 3 corruption subtypes. A change covering both gates would be multi-axis and tuned to this development screen.

## Decision

Stop Terra on this screen. Do not tune or rerun Terra against these 48 cases. The next experiment is a predeclared, fresh Sol screen whose cases do not overlap this development screen.
