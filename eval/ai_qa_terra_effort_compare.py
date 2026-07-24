from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from eval.ai_qa_luna_effort_compare import _case_correct, _parse
from eval.ai_qa_scorer import (
    TRUTH_FIELD_TO_ERROR_FIELD,
    load_jsonl,
    score_predictions,
)
from eval.ai_qa_terra_effort_screen import (
    DEFAULT_TERRA_EFFORT_SCREEN_DIR,
    SCREEN_SPLIT,
)


EVAL_ROOT = Path(__file__).resolve().parent
NONE_RUN_DIR = EVAL_ROOT / "runs" / "terra-effort-screen-none"
LOW_RUN_DIR = EVAL_ROOT / "runs" / "terra-effort-screen-low"
OUTPUT_DIR = EVAL_ROOT / "runs" / "terra-effort-screen-comparison"


def _profile(
    truth_rows: Sequence[Mapping[str, object]],
    prediction_rows: Sequence[Mapping[str, object]],
) -> dict[str, Any]:
    truth_by_id = {str(row["case_id"]): row for row in truth_rows}
    prediction_by_id = {str(row["case_id"]): row for row in prediction_rows}
    if set(truth_by_id) != set(prediction_by_id):
        raise ValueError("Terra-screen truth and prediction IDs differ")
    counts: Counter[str] = Counter()
    for case_id, truth in truth_by_id.items():
        prediction = prediction_by_id[case_id]
        covered, _has_error, _field = _parse(prediction)
        counts["covered"] += int(covered)
        counts["technical_failures"] += int(
            prediction.get("status") == "technical_failure"
        )
        correct, has_error, error_field = _case_correct(truth, prediction)
        counts["total_correct"] += int(correct)
        if truth["case_type"] == "clean":
            counts["clean_cases"] += 1
            counts["false_alerts"] += int(has_error)
            continue
        expected = TRUTH_FIELD_TO_ERROR_FIELD[str(truth["corrupted_field"])]
        if expected == "wbs":
            counts["wbs_cases"] += 1
            counts["correct_wbs"] += int(correct)
        else:
            counts["non_wbs_cases"] += 1
            counts["correct_non_wbs"] += int(correct)
            counts["non_wbs_diverted_to_wbs"] += int(
                has_error and error_field == "wbs"
            )
    report = score_predictions(
        truth_rows,
        prediction_rows,
        split=SCREEN_SPLIT,
        run_label="terra-reasoning-screen",
    )
    keys = (
        "covered",
        "technical_failures",
        "total_correct",
        "clean_cases",
        "false_alerts",
        "wbs_cases",
        "correct_wbs",
        "non_wbs_cases",
        "correct_non_wbs",
        "non_wbs_diverted_to_wbs",
    )
    return {
        **{key: counts[key] for key in keys},
        "coverage": counts["covered"] / len(truth_rows),
        "operational": report["operational"],
    }


def compare_terra_efforts(
    *,
    truth_rows: Sequence[Mapping[str, object]],
    none_rows: Sequence[Mapping[str, object]],
    low_rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    none = _profile(truth_rows, none_rows)
    low = _profile(truth_rows, low_rows)
    truth_by_id = {str(row["case_id"]): row for row in truth_rows}
    none_by_id = {str(row["case_id"]): row for row in none_rows}
    low_by_id = {str(row["case_id"]): row for row in low_rows}
    paired: Counter[str] = Counter()
    for case_id, truth in truth_by_id.items():
        none_correct = _case_correct(truth, none_by_id[case_id])[0]
        low_correct = _case_correct(truth, low_by_id[case_id])[0]
        if none_correct and low_correct:
            paired["both_correct"] += 1
        elif none_correct:
            paired["none_only_correct"] += 1
        elif low_correct:
            paired["low_only_correct"] += 1
        else:
            paired["both_wrong"] += 1
    criteria = {
        "low_coverage_100_percent": low["coverage"] == 1.0,
        "low_zero_technical_failures": low["technical_failures"] == 0,
        "low_correct_wbs_at_least_18_of_20": low["correct_wbs"] >= 18,
        "low_false_alerts_at_most_1_of_16": low["false_alerts"] <= 1,
        "low_correct_non_wbs_at_least_11_of_12": (
            low["correct_non_wbs"] >= 11
        ),
        "low_total_correct_at_least_44_of_48": low["total_correct"] >= 44,
        "low_does_not_reduce_total_correct": (
            low["total_correct"] >= none["total_correct"]
        ),
    }
    advance_low = all(criteria.values())
    return {
        "experiment": "synthetic offline Terra reasoning-effort screen",
        "evidence_scope": "development diagnostic; not calibration or validation",
        "none": none,
        "low": low,
        "delta_low_minus_none": {
            key: low[key] - none[key]
            for key in (
                "correct_wbs",
                "false_alerts",
                "correct_non_wbs",
                "total_correct",
            )
        },
        "paired_outcomes": dict(paired),
        "selection_criteria": criteria,
        "decision": (
            "advance_terra_low_to_fresh_calibration_contract"
            if advance_low
            else "stop_terra"
        ),
        "locked_holdout_used": False,
        "luna_low_validation_used": False,
        "sol_used": False,
    }


def _markdown(comparison: Mapping[str, object]) -> str:
    none = comparison["none"]
    low = comparison["low"]
    criteria = comparison["selection_criteria"]
    lines = [
        "# Terra Reasoning-Effort Screen",
        "",
        "Development diagnostic only; not calibration or validation evidence.",
        "",
        "| Measure | none | low |",
        "|---|---:|---:|",
        f"| Correct WBS | {none['correct_wbs']}/20 | {low['correct_wbs']}/20 |",
        f"| Clean false alerts | {none['false_alerts']}/16 | {low['false_alerts']}/16 |",
        f"| Correct non-WBS | {none['correct_non_wbs']}/12 | {low['correct_non_wbs']}/12 |",
        f"| Total correct | {none['total_correct']}/48 | {low['total_correct']}/48 |",
        f"| Coverage | {none['coverage']:.1%} | {low['coverage']:.1%} |",
        "",
        "## Selection criteria",
        "",
        *(f"- {name}: {'pass' if passed else 'fail'}" for name, passed in criteria.items()),
        "",
        f"Decision: `{comparison['decision']}`.",
        "",
        "The locked holdout, Luna-low validation, and Sol were not used.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    truth_rows = load_jsonl(DEFAULT_TERRA_EFFORT_SCREEN_DIR / "truth.jsonl")
    comparison = compare_terra_efforts(
        truth_rows=truth_rows,
        none_rows=load_jsonl(NONE_RUN_DIR / "predictions.jsonl"),
        low_rows=load_jsonl(LOW_RUN_DIR / "predictions.jsonl"),
    )
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUTPUT_DIR / "comparison.json"
    markdown_path = OUTPUT_DIR / "comparison.md"
    json_path.write_text(
        json.dumps(comparison, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(_markdown(comparison), encoding="utf-8")
    print(json.dumps(comparison, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
