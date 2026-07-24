from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path

from eval.ai_qa_luna_effort_compare import _case_correct
from eval.ai_qa_reports import write_report_bundle
from eval.ai_qa_scorer import load_jsonl, score_predictions
from eval.ai_qa_terra_effort_compare import _profile
from eval.ai_qa_terra_prompt_reasoning_screen import (
    DEFAULT_TERRA_PROMPT_REASONING_SCREEN_DIR,
)


EVAL_ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = EVAL_ROOT / "runs" / "terra-2x2-comparison"
PROFILE_DIRS = {
    "luna-v5-low": EVAL_ROOT / "runs" / "terra-2x2-luna-v5-low",
    "terra-v1-low": EVAL_ROOT / "runs" / "terra-2x2-terra-v1-low",
    "luna-v5-medium": EVAL_ROOT / "runs" / "terra-2x2-luna-v5-medium",
    "terra-v1-medium": EVAL_ROOT / "runs" / "terra-2x2-terra-v1-medium",
}


def _paired(
    truth_rows: Sequence[Mapping[str, object]],
    left_rows: Sequence[Mapping[str, object]],
    right_rows: Sequence[Mapping[str, object]],
) -> dict[str, int]:
    truth = {str(row["case_id"]): row for row in truth_rows}
    left = {str(row["case_id"]): row for row in left_rows}
    right = {str(row["case_id"]): row for row in right_rows}
    if not (set(truth) == set(left) == set(right)):
        raise ValueError("Terra 2x2 comparison IDs differ")
    counts: Counter[str] = Counter()
    for case_id, expected in truth.items():
        left_ok = _case_correct(expected, left[case_id])[0]
        right_ok = _case_correct(expected, right[case_id])[0]
        if left_ok and right_ok:
            counts["both_correct"] += 1
        elif left_ok:
            counts["left_only_correct"] += 1
        elif right_ok:
            counts["right_only_correct"] += 1
        else:
            counts["both_wrong"] += 1
    return {key: counts[key] for key in ("both_correct", "left_only_correct", "right_only_correct", "both_wrong")}


def compare_profiles(
    *,
    truth_rows: Sequence[Mapping[str, object]],
    predictions: Mapping[str, Sequence[Mapping[str, object]]],
) -> dict[str, object]:
    profiles = {name: _profile(truth_rows, rows) for name, rows in predictions.items()}
    eligibility = {
        name: {
            "coverage_100_percent": profile["coverage"] == 1.0,
            "zero_technical_failures": profile["technical_failures"] == 0,
            "correct_wbs_at_least_18_of_20": profile["correct_wbs"] >= 18,
            "false_alerts_at_most_1_of_16": profile["false_alerts"] <= 1,
            "correct_non_wbs_at_least_11_of_12": profile["correct_non_wbs"] >= 11,
            "total_correct_at_least_44_of_48": profile["total_correct"] >= 44,
        }
        for name, profile in profiles.items()
    }
    eligible = [name for name, gates in eligibility.items() if all(gates.values())]
    ranked = sorted(
        eligible,
        key=lambda name: (
            -profiles[name]["total_correct"],
            -profiles[name]["correct_wbs"],
            -profiles[name]["correct_non_wbs"],
            profiles[name]["false_alerts"],
            profiles[name]["operational"]["cost"]["total_usd"],
            name,
        ),
    )
    comparisons = {
        "prompt_effect_at_low_left_luna_right_terra": _paired(
            truth_rows, predictions["luna-v5-low"], predictions["terra-v1-low"]
        ),
        "prompt_effect_at_medium_left_luna_right_terra": _paired(
            truth_rows, predictions["luna-v5-medium"], predictions["terra-v1-medium"]
        ),
        "reasoning_effect_luna_v5_left_low_right_medium": _paired(
            truth_rows, predictions["luna-v5-low"], predictions["luna-v5-medium"]
        ),
        "reasoning_effect_terra_v1_left_low_right_medium": _paired(
            truth_rows, predictions["terra-v1-low"], predictions["terra-v1-medium"]
        ),
    }
    return {
        "experiment": "synthetic offline Terra prompt x reasoning screen",
        "evidence_scope": "development diagnostic; not calibration or validation",
        "profiles": profiles,
        "eligibility": eligibility,
        "paired_comparisons": comparisons,
        "eligible_profiles": ranked,
        "decision": (
            {"action": "advance_to_fresh_calibration_contract", "selected_profile": ranked[0]}
            if ranked
            else {"action": "stop_terra", "selected_profile": None}
        ),
        "combined_estimated_cost_usd": sum(
            profile["operational"]["cost"]["total_usd"] for profile in profiles.values()
        ),
        "locked_holdout_used": False,
        "luna_low_validation_used": False,
        "sol_used": False,
    }


def _markdown(result: Mapping[str, object]) -> str:
    lines = [
        "# Terra Prompt × Reasoning Screen",
        "",
        "Development diagnostic only; not calibration or validation evidence.",
        "",
        "| Profile | WBS | False alerts | Non-WBS | Total | Cost | Eligible |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for name, profile in result["profiles"].items():
        eligible = all(result["eligibility"][name].values())
        lines.append(
            f"| {name} | {profile['correct_wbs']}/20 | {profile['false_alerts']}/16 | "
            f"{profile['correct_non_wbs']}/12 | {profile['total_correct']}/48 | "
            f"${profile['operational']['cost']['total_usd']:.6f} | {'yes' if eligible else 'no'} |"
        )
    lines.extend([
        "",
        f"Decision: `{result['decision']['action']}`; selected profile: "
        f"`{result['decision']['selected_profile']}`.",
        "",
        f"Combined estimated cost: `${result['combined_estimated_cost_usd']:.6f}`.",
        "",
        "The locked holdout, Luna-low validation, and Sol were not used.",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    truth = load_jsonl(DEFAULT_TERRA_PROMPT_REASONING_SCREEN_DIR / "truth.jsonl")
    predictions = {name: load_jsonl(path / "predictions.jsonl") for name, path in PROFILE_DIRS.items()}
    for name, rows in predictions.items():
        report = score_predictions(
            truth,
            rows,
            split="terra_prompt_reasoning_screen",
            run_label=name,
        )
        write_report_bundle(report, PROFILE_DIRS[name] / "reports")
    result = compare_profiles(truth_rows=truth, predictions=predictions)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "comparison.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUTPUT_DIR / "comparison.md").write_text(_markdown(result), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
