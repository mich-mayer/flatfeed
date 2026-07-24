# Luna-v4 Failure Audit

Synthetic offline calibration diagnostics. The locked holdout was not used.

## Aggregate finding

- Clean false alerts: 19; WBS predictions: 19.
- Wrong field localizations: 13; diverted to WBS: 11.
- WBS localized misses: 2.

## Highest-risk WBS wording variants

| Expected WBS | Wording | Clean FP | Non-WBS diverted to WBS | WBS misses |
|---|---|---:|---:|---:|
| 160, 180, 220 | Zulassung ab einer Einkommensgrenze von 141 % bis einschließlich WBS 220 %. | 4 | 1 | 0 |
| 160, 180, 220 | WBS-Bereich: 141 % bis 220 %, beide genannten Grenzen eingeschlossen. | 1 | 3 | 0 |
| 160, 180, 220 | Für diese Wohnung gilt ein WBS oberhalb von 140 % und höchstens 220 %. | 2 | 2 | 0 |
| 140, 160, 180, 220 | Die untere WBS-Grenze von 140 % ist eingeschlossen; die Obergrenze liegt bei 220 %. | 3 | 1 | 0 |
| 140, 160, 180, 220 | Voraussetzung: mindestens WBS 140 und höchstens WBS 220. | 1 | 2 | 0 |
| 160, 180, 220 | Ein WBS 140 berechtigt nicht; zugelassen sind 160 %, 180 % und 220 %. | 3 | 0 | 0 |
| 100, 140, 160, 180 | Die WBS-Obergrenze liegt bei 180 %. | 2 | 1 | 0 |
| 140, 160, 180, 220 | Zulässig ist ein WBS von 140 % bis einschließlich 220 %. | 2 | 0 | 0 |
| 100, 140, 160, 180 | Berechtigung: WBS 100–180 %, einschließlich beider Grenzen. | 1 | 0 | 0 |
| 100, 140 | Berechtigung: WBS 100–140 %, beide Grenzen eingeschlossen. | 0 | 1 | 0 |
| 100 | Zugelassen ist ausschließlich die WBS-Stufe 100 %. | 0 | 0 | 1 |
| 100 | Die Wohnung ist ausschließlich für einen WBS 100 vorgesehen. | 0 | 0 | 1 |

## Decision

The dominant failure is WBS salience: the checker treats semantically unusual but correct WBS wording as a contradiction and can stop before localizing the actual non-WBS error. The next cycle must audit wording validity, add clean negative controls, and reduce field-order bias before another paid calibration.
