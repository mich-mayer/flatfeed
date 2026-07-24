from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path

from eval.ai_qa_luna_effort_compare import _case_correct
from eval.ai_qa_reports import write_report_bundle
from eval.ai_qa_scorer import load_jsonl, score_predictions
from eval.ai_qa_terra_high_screen import DEFAULT_TERRA_HIGH_SCREEN_DIR


EVAL_ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = EVAL_ROOT / "runs" / "terra-high-screen-comparison"
PROFILE_DIRS = {
    "terra-v1-medium": EVAL_ROOT / "runs" / "terra-high-screen-medium",
    "terra-v1-high": EVAL_ROOT / "runs" / "terra-high-screen-high",
}


def _profile(
    truth_rows: Sequence[Mapping[str, object]],
    prediction_rows: Sequence[Mapping[str, object]],
    *,
    name: str,
) -> dict[str, object]:
    report = score_predictions(
        truth_rows,
        prediction_rows,
        split="terra_high_reasoning_screen",
        run_label=name,
    )
    total_correct = sum(
        _case_correct(truth, prediction)[0]
        for truth, prediction in zip(
            sorted(truth_rows, key=lambda row: str(row["case_id"])),
            sorted(prediction_rows, key=lambda row: str(row["case_id"])),
        )
    )
    fields = report["field_breakdown"]
    correct_other = sum(
        int(row["correctly_localized"])
        for field, row in fields.items()
        if field not in {"wbs", "rooms"}
    )
    operational = dict(report["operational"])
    if operational.get("cost") is None:
        operational["cost"] = {
            "total_usd": 0.0,
            "is_partial": True,
            "records_with_cost": 0,
            "total_case_records": len(prediction_rows),
        }
    return {
        "coverage": report["metrics"]["structured_output_coverage"]["value"],
        "technical_failures": report["counts"]["technical_failures"],
        "correct_rooms": fields["rooms"]["correctly_localized"],
        "correct_wbs": fields["wbs"]["correctly_localized"],
        "correct_other_fields": correct_other,
        "false_alerts": report["counts"]["false_positives"],
        "total_correct": total_correct,
        "operational": operational,
    }


def _paired(
    truth_rows: Sequence[Mapping[str, object]],
    medium_rows: Sequence[Mapping[str, object]],
    high_rows: Sequence[Mapping[str, object]],
) -> dict[str, int]:
    truth = {str(row["case_id"]): row for row in truth_rows}
    medium = {str(row["case_id"]): row for row in medium_rows}
    high = {str(row["case_id"]): row for row in high_rows}
    if not (set(truth) == set(medium) == set(high)):
        raise ValueError("Terra medium/high comparison IDs differ")
    counts: Counter[str] = Counter()
    for case_id, expected in truth.items():
        medium_ok = _case_correct(expected, medium[case_id])[0]
        high_ok = _case_correct(expected, high[case_id])[0]
        if medium_ok and high_ok:
            counts["both_correct"] += 1
        elif medium_ok:
            counts["medium_only_correct"] += 1
        elif high_ok:
            counts["high_only_correct"] += 1
        else:
            counts["both_wrong"] += 1
    return {
        key: counts[key]
        for key in (
            "both_correct",
            "medium_only_correct",
            "high_only_correct",
            "both_wrong",
        )
    }


def compare_terra_high_profiles(
    *,
    truth_rows: Sequence[Mapping[str, object]],
    medium_rows: Sequence[Mapping[str, object]],
    high_rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    profiles = {
        "terra-v1-medium": _profile(
            truth_rows,
            medium_rows,
            name="terra-v1-medium",
        ),
        "terra-v1-high": _profile(
            truth_rows,
            high_rows,
            name="terra-v1-high",
        ),
    }
    medium = profiles["terra-v1-medium"]
    high = profiles["terra-v1-high"]
    absolute = {
        "coverage_100_percent": high["coverage"] == 1.0,
        "zero_technical_failures": high["technical_failures"] == 0,
        "correct_rooms_at_least_13_of_14": high["correct_rooms"] >= 13,
        "correct_wbs_at_least_13_of_14": high["correct_wbs"] >= 13,
        "false_alerts_at_most_1_of_12": high["false_alerts"] <= 1,
        "correct_other_fields_at_least_7_of_8": (
            high["correct_other_fields"] >= 7
        ),
        "total_correct_at_least_45_of_48": high["total_correct"] >= 45,
    }
    comparative = {
        "at_least_one_additional_total_correct_case": (
            high["total_correct"] >= medium["total_correct"] + 1
        ),
        "at_least_one_additional_matching_critical_case": (
            high["correct_rooms"] + high["correct_wbs"]
            >= medium["correct_rooms"] + medium["correct_wbs"] + 1
        ),
        "no_wbs_regression": high["correct_wbs"] >= medium["correct_wbs"],
        "no_rooms_regression": high["correct_rooms"] >= medium["correct_rooms"],
        "no_clean_false_alert_regression": (
            high["false_alerts"] <= medium["false_alerts"]
        ),
        "no_other_field_regression": (
            high["correct_other_fields"] >= medium["correct_other_fields"]
        ),
    }
    advances = all(absolute.values()) and all(comparative.values())
    return {
        "experiment": "synthetic offline Terra medium-vs-high reasoning screen",
        "evidence_scope": "development diagnostic; not calibration or validation",
        "profiles": profiles,
        "advancement": {
            "absolute": absolute,
            "comparative": comparative,
            "all_criteria_pass": advances,
        },
        "paired_comparison": _paired(truth_rows, medium_rows, high_rows),
        "decision": {
            "action": (
                "advance_terra_high_to_fresh_calibration_contract"
                if advances
                else "stop_terra_reasoning_escalation"
            ),
            "selected_profile": "terra-v1-high" if advances else None,
        },
        "combined_recorded_cost_usd": sum(
            float(profile["operational"]["cost"]["total_usd"])
            for profile in profiles.values()
        ),
        "consumed_validation_reused": False,
        "locked_holdout_used": False,
        "sol_used": False,
    }


def _markdown(result: Mapping[str, object]) -> str:
    lines = [
        "# Terra Medium vs High Reasoning Screen",
        "",
        "Development diagnostic only; not calibration or validation evidence.",
        "",
        "| Profile | rooms | WBS | Clean false alerts | Other fields | Total | Cost |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name, profile in result["profiles"].items():
        lines.append(
            f"| {name} | {profile['correct_rooms']}/14 | "
            f"{profile['correct_wbs']}/14 | {profile['false_alerts']}/12 | "
            f"{profile['correct_other_fields']}/8 | "
            f"{profile['total_correct']}/48 | "
            f"${profile['operational']['cost']['total_usd']:.6f} |"
        )
    lines.extend(
        [
            "",
            f"Decision: `{result['decision']['action']}`; selected profile: "
            f"`{result['decision']['selected_profile']}`.",
            "",
            f"Combined recorded cost: "
            f"`${result['combined_recorded_cost_usd']:.6f}`.",
            "",
            "The consumed validation, locked holdout, and Sol were not used.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    if (OUTPUT_DIR / "comparison.json").exists() or (
        OUTPUT_DIR / "comparison.md"
    ).exists():
        raise FileExistsError("Terra high comparison artifacts already exist")
    truth = load_jsonl(DEFAULT_TERRA_HIGH_SCREEN_DIR / "truth.jsonl")
    predictions = {
        name: load_jsonl(path / "predictions.jsonl")
        for name, path in PROFILE_DIRS.items()
    }
    for name, rows in predictions.items():
        report = score_predictions(
            truth,
            rows,
            split="terra_high_reasoning_screen",
            run_label=name,
        )
        write_report_bundle(report, PROFILE_DIRS[name] / "reports")
    result = compare_terra_high_profiles(
        truth_rows=truth,
        medium_rows=predictions["terra-v1-medium"],
        high_rows=predictions["terra-v1-high"],
    )
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "comparison.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (OUTPUT_DIR / "comparison.md").write_text(
        _markdown(result),
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
