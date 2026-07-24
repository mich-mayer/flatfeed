# Luna-low Calibration Failure Audit

Synthetic offline calibration diagnostics only. No validation, locked holdout, or new model call was used.

## Outcome

- False negatives: 8 of 140 corrupted cases.
- Clean false alerts: 0 of 140 clean cases.
- Wrong field localizations: 0.
- WBS: 50/56; minimum 51 required; status **fail**.

## Misses by field

| Field | Cases | Misses | Localized recall |
|---|---:|---:|---:|
| wbs | 56 | 6 | 89.3% |
| address_postal_code | 14 | 1 | 92.9% |
| district | 10 | 1 | 90.0% |
| rooms | 21 | 0 | 100.0% |
| rent_kalt | 21 | 0 | 100.0% |
| floor | 10 | 0 | 100.0% |
| rent_warm | 8 | 0 | 100.0% |

## WBS misses by semantic family

| Expected normalized WBS | Cases | Misses | Localized recall |
|---|---:|---:|---:|
| WBS required, type unknown | 8 | 2 | 75.0% |
| No WBS required | 8 | 2 | 75.0% |
| 100, 140, 160, 180 | 8 | 1 | 87.5% |
| 100 | 8 | 1 | 87.5% |
| 160, 180, 220 | 8 | 0 | 100.0% |
| 140, 160, 180, 220 | 8 | 0 | 100.0% |
| 100, 140 | 8 | 0 | 100.0% |

## WBS misses by corruption subtype

| Corruption subtype | Cases | Misses | Localized recall |
|---|---:|---:|---:|
| wbs_range_boundary_shift | 37 | 2 | 94.6% |
| wbs_requirement_added | 8 | 2 | 75.0% |
| wbs_requirement_dropped | 10 | 1 | 90.0% |
| wbs_specificity_confusion | 1 | 1 | 0.0% |

## Missed WBS transitions

| Expected -> corrupted | Exposures | Misses |
|---|---:|---:|
| WBS required, type unknown -> No WBS required | 7 | 1 |
| No WBS required -> 100 | 5 | 1 |
| 100, 140, 160, 180 -> 100, 140, 160, 180, 220 | 5 | 1 |
| 100 -> 100, 140 | 5 | 1 |
| No WBS required -> WBS required, type unknown | 3 | 1 |
| WBS required, type unknown -> 100 | 1 | 1 |

## Aggregate pattern

- 4 of 6 WBS misses occurred in the `No WBS required` or generic `WBS required, type unknown` families.
- The 6 WBS misses used 6 distinct transitions; the maximum count for one transition was 1.
- Zero-miss WBS families: `100, 140`, `140, 160, 180, 220`, `160, 180, 220`.
- Caution: Subtype and family counts are diagnostic calibration slices, not independent performance estimates.

## Cross-cycle context

Different fresh calibration inputs were used, so this comparison is descriptive and must not be interpreted as a paired causal effect.

- WBS localized misses: 11/56 with Luna-v5 none; 6/56 with Luna-v5 low.
- Clean false alerts: 5/140 with none; 0/140 with low.
- Wrong field localizations: 4 with none; 0 with low.

## Decision

Calibration remains failed. Do not freeze the configuration, run validation, rerun calibration, or tune the prompt against these cases. The next decision is whether to close Luna with this measured limitation or authorize a separately predeclared stronger-model experiment using new data.
