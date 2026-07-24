# Luna-v5 Failure Audit

Synthetic offline calibration diagnostics. The locked holdout was not used.

## Aggregate finding

- Clean false alerts: 5; WBS predictions: 5.
- Wrong field localizations: 4; diverted to WBS: 3.
- WBS localized misses: 11.

## Highest-risk WBS wording variants

| Expected WBS | Wording | Clean FP | Non-WBS diverted to WBS | WBS misses |
|---|---|---:|---:|---:|
| 140, 160, 180, 220 | Ab WBS 140 bis WBS 220 sind alle unterstützten Stufen zulässig. | 2 | 1 | 0 |
| 100, 140, 160, 180 | Zulässig ist ein WBS 100-180 %. | 1 | 1 | 0 |
| 140, 160, 180, 220 | Zulässig ist ein WBS 140-220 %. | 1 | 0 | 0 |
| 100 | WBS-Bindung: 100 %, keine weitere Stufe. | 0 | 1 | 0 |
| 140, 160, 180, 220 | Akzeptiert wird ein WBS von 140 % bis einschließlich 220 %. | 1 | 0 | 0 |
| 100, 140 | WBS-Obergrenze 140 %; zulässige Stufen sind 100 % und 140 %. | 0 | 0 | 2 |
| 100 | Voraussetzung ist ausschließlich ein WBS 100. | 0 | 0 | 2 |
| 100, 140, 160, 180 | Eine Bewerbung ist bis WBS 180 möglich. | 0 | 0 | 2 |
| 100, 140 | Akzeptiert wird ein WBS bis einschließlich 140 %. | 0 | 0 | 2 |
| WBS required, type unknown | Nur mit Wohnberechtigungsschein, Förderstufe nicht angegeben. | 0 | 0 | 1 |
| No WBS required | Für dieses Angebot wird kein WBS verlangt. | 0 | 0 | 1 |
| 100 | Bewerbung nur mit Wohnberechtigungsschein 100. | 0 | 0 | 1 |

## Decision

The dominant failure is WBS salience: the checker treats semantically unusual but correct WBS wording as a contradiction and can stop before localizing the actual non-WBS error. The next cycle must audit wording validity, add clean negative controls, and reduce field-order bias before another paid calibration.
