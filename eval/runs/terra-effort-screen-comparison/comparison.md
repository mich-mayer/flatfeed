# Terra Reasoning-Effort Screen

Development diagnostic only; not calibration or validation evidence.

| Measure | none | low |
|---|---:|---:|
| Correct WBS | 16/20 | 17/20 |
| Clean false alerts | 0/16 | 0/16 |
| Correct non-WBS | 10/12 | 10/12 |
| Total correct | 42/48 | 43/48 |
| Coverage | 100.0% | 100.0% |

## Selection criteria

- low_coverage_100_percent: pass
- low_zero_technical_failures: pass
- low_correct_wbs_at_least_18_of_20: fail
- low_false_alerts_at_most_1_of_16: pass
- low_correct_non_wbs_at_least_11_of_12: fail
- low_total_correct_at_least_44_of_48: fail
- low_does_not_reduce_total_correct: pass

Decision: `stop_terra`.

The locked holdout, Luna-low validation, and Sol were not used.
