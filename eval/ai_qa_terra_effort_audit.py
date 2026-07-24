from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path

from eval.ai_qa_luna_effort_compare import _case_correct
from eval.ai_qa_luna_v4_audit import _find_wbs_phrase
from eval.ai_qa_luna_v5_cycle import LUNA_V5_WBS_PHRASES
from eval.ai_qa_scorer import TRUTH_FIELD_TO_ERROR_FIELD, load_jsonl
from eval.ai_qa_terra_effort_screen import DEFAULT_TERRA_EFFORT_SCREEN_DIR


EVAL_ROOT = Path(__file__).resolve().parent
NONE_RUN_DIR = EVAL_ROOT / "runs" / "terra-effort-screen-none"
LOW_RUN_DIR = EVAL_ROOT / "runs" / "terra-effort-screen-low"
COMPARISON_DIR = EVAL_ROOT / "runs" / "terra-effort-screen-comparison"
INPUT_PATH = DEFAULT_TERRA_EFFORT_SCREEN_DIR / "model_inputs.jsonl"
TRUTH_PATH = DEFAULT_TERRA_EFFORT_SCREEN_DIR / "truth.jsonl"


def _index_rows(
    rows: Sequence[Mapping[str, object]], *, label: str
) -> dict[str, Mapping[str, object]]:
    indexed = {str(row["case_id"]): row for row in rows}
    if len(indexed) != len(rows):
        raise ValueError(f"{label} contains duplicate case IDs")
    return indexed


def _rate(correct: int, total: int) -> float:
    return correct / total if total else 0.0


def _outcome_rows(
    exposures: Counter[str], misses: Counter[str], *, key_name: str
) -> list[dict[str, object]]:
    return [
        {
            key_name: key,
            "exposures": exposures[key],
            "misses": misses[key],
            "correct": exposures[key] - misses[key],
            "recall": _rate(exposures[key] - misses[key], exposures[key]),
        }
        for key in sorted(
            exposures,
            key=lambda value: (misses[value], exposures[value], value),
            reverse=True,
        )
    ]


def build_terra_effort_failure_audit(
    *,
    input_rows: Sequence[Mapping[str, object]],
    truth_rows: Sequence[Mapping[str, object]],
    none_rows: Sequence[Mapping[str, object]],
    low_rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    inputs = _index_rows(input_rows, label="inputs")
    truth = _index_rows(truth_rows, label="truth")
    none = _index_rows(none_rows, label="none predictions")
    low = _index_rows(low_rows, label="low predictions")
    if not (set(inputs) == set(truth) == set(none) == set(low)):
        raise ValueError("Terra audit input, truth, and prediction IDs differ")

    field_exposures: Counter[str] = Counter()
    field_misses: Counter[str] = Counter()
    subtype_exposures: Counter[str] = Counter()
    subtype_misses: Counter[str] = Counter()
    wbs_family_exposures: Counter[str] = Counter()
    wbs_family_misses: Counter[str] = Counter()
    paired: Counter[str] = Counter()
    paired_by_field: dict[str, Counter[str]] = {}
    totals: Counter[str] = Counter()

    for case_id, truth_row in truth.items():
        none_correct = _case_correct(truth_row, none[case_id])[0]
        low_correct = _case_correct(truth_row, low[case_id])[0]
        if none_correct and low_correct:
            paired_key = "both_correct"
        elif none_correct:
            paired_key = "none_only_correct"
        elif low_correct:
            paired_key = "low_only_correct"
        else:
            paired_key = "both_wrong"
        paired[paired_key] += 1

        if truth_row.get("case_type") == "clean":
            field = "clean"
            totals["clean_cases"] += 1
        else:
            corrupted_field = truth_row.get("corrupted_field")
            if not isinstance(corrupted_field, str):
                raise ValueError("corrupted truth row lacks corrupted_field")
            field = TRUTH_FIELD_TO_ERROR_FIELD[corrupted_field]
            totals["corrupted_cases"] += 1
            field_exposures[field] += 1
            corruption_type = truth_row.get("corruption_type")
            if not isinstance(corruption_type, str):
                raise ValueError("corrupted truth row lacks corruption_type")
            subtype_key = f"{field}:{corruption_type}"
            subtype_exposures[subtype_key] += 1
            if not low_correct:
                totals["low_misses"] += 1
                field_misses[field] += 1
                subtype_misses[subtype_key] += 1
            if field == "wbs":
                _phrase, family = _find_wbs_phrase(
                    str(inputs[case_id]["raw_text"]),
                    wbs_phrases=LUNA_V5_WBS_PHRASES,
                )
                wbs_family_exposures[family] += 1
                if not low_correct:
                    wbs_family_misses[family] += 1
        paired_by_field.setdefault(field, Counter())[paired_key] += 1

    failed_fields = sorted(
        field for field, misses in field_misses.items() if misses
    )
    missed_subtypes = sorted(
        subtype for subtype, misses in subtype_misses.items() if misses
    )
    postal_exposures = subtype_exposures[
        "address_postal_code:postal_code_substitution"
    ]
    postal_both_wrong = paired_by_field.get(
        "address_postal_code", Counter()
    )["both_wrong"]
    distinct_wbs_missed_subtypes = sum(
        1
        for key, misses in subtype_misses.items()
        if key.startswith("wbs:") and misses
    )
    return {
        "experiment": "synthetic offline Terra reasoning-screen failure audit",
        "evidence_scope": (
            "aggregate development diagnostics only; not calibration, "
            "validation, or a causal prompt test"
        ),
        "configuration": {
            "model": "gpt-5.6-terra",
            "reasoning_effort": "low",
            "prompt_version": "luna-v5",
        },
        "totals": {
            "clean_cases": totals["clean_cases"],
            "corrupted_cases": totals["corrupted_cases"],
            "low_misses": totals["low_misses"],
        },
        "low_outcomes_by_field": _outcome_rows(
            field_exposures, field_misses, key_name="field"
        ),
        "low_outcomes_by_corruption_subtype": _outcome_rows(
            subtype_exposures, subtype_misses, key_name="field_and_subtype"
        ),
        "low_wbs_outcomes_by_semantic_family": _outcome_rows(
            wbs_family_exposures,
            wbs_family_misses,
            key_name="semantic_family",
        ),
        "paired_outcomes": {
            key: paired[key]
            for key in (
                "both_correct",
                "low_only_correct",
                "none_only_correct",
                "both_wrong",
            )
        },
        "paired_outcomes_by_field": {
            field: {
                key: counts[key]
                for key in (
                    "both_correct",
                    "low_only_correct",
                    "none_only_correct",
                    "both_wrong",
                )
            }
            for field, counts in sorted(paired_by_field.items())
        },
        "aggregate_observations": {
            "failed_fields": failed_fields,
            "missed_corruption_subtypes": missed_subtypes,
            "distinct_failed_fields": len(failed_fields),
            "distinct_missed_corruption_subtypes": len(missed_subtypes),
            "postal_code_substitution": {
                "exposures": postal_exposures,
                "low_misses": subtype_misses[
                    "address_postal_code:postal_code_substitution"
                ],
                "both_wrong": postal_both_wrong,
            },
            "wbs_misses": field_misses["wbs"],
            "distinct_missed_wbs_subtypes": distinct_wbs_missed_subtypes,
            "small_subgroup_caution": (
                "The screen is a 48-case development diagnostic; subtype "
                "counts are not independent performance estimates."
            ),
        },
        "prompt_hypothesis_assessment": {
            "prompt_may_contribute": True,
            "reason": (
                f"{postal_both_wrong}/{postal_exposures} postal-code "
                "substitutions were missed by both Terra configurations, "
                f"while low also missed {distinct_wbs_missed_subtypes} WBS "
                "subtypes."
            ),
            "single_narrow_prompt_change_supported": False,
            "reason_not_supported": (
                "The failed advancement gates span address/postal-code and WBS, "
                f"and the WBS misses span {distinct_wbs_missed_subtypes} "
                "corruption subtypes. A change "
                "covering both gates would be multi-axis and tuned to this "
                "development screen."
            ),
        },
        "boundaries": {
            "contains_case_ids": False,
            "contains_raw_listing_text": False,
            "contains_parser_snapshots": False,
            "contains_exact_field_values": False,
            "new_model_calls": False,
            "prompt_tuning_authorized": False,
            "screen_rerun_authorized": False,
            "calibration_authorized": False,
            "validation_used": False,
            "locked_holdout_used": False,
            "sol_used": False,
        },
        "decision": {
            "terra_status": "stop",
            "action": "do_not_tune_or_rerun_terra_on_this_screen",
            "next_experiment": (
                "predeclare a fresh independent Sol reasoning/configuration "
                "screen without using Terra screen cases"
            ),
        },
    }


def _percent(value: object) -> str:
    return f"{float(value) * 100:.1f}%"


def render_markdown(audit: Mapping[str, object]) -> str:
    totals = audit["totals"]
    observations = audit["aggregate_observations"]
    hypothesis = audit["prompt_hypothesis_assessment"]
    rows = [
        "# Terra Reasoning-Screen Failure Audit",
        "",
        "Aggregate development diagnostics only. No new model call, validation, "
        "locked holdout, or Sol run was used.",
        "",
        "## Outcome",
        "",
        f"- Terra-low misses: {totals['low_misses']} of "
        f"{totals['corrupted_cases']} corrupted cases.",
        f"- Failed fields: {', '.join(observations['failed_fields'])}.",
        "",
        "## Terra-low outcomes by field",
        "",
        "| Field | Cases | Misses | Recall |",
        "|---|---:|---:|---:|",
    ]
    for row in audit["low_outcomes_by_field"]:
        rows.append(
            f"| {row['field']} | {row['exposures']} | {row['misses']} | "
            f"{_percent(row['recall'])} |"
        )
    rows.extend(
        [
            "",
            "## Missed corruption subtypes",
            "",
            "| Field and subtype | Cases | Misses | Recall |",
            "|---|---:|---:|---:|",
        ]
    )
    for row in audit["low_outcomes_by_corruption_subtype"]:
        if row["misses"]:
            rows.append(
                f"| {row['field_and_subtype']} | {row['exposures']} | "
                f"{row['misses']} | {_percent(row['recall'])} |"
            )
    rows.extend(
        [
            "",
            "## Paired evidence",
            "",
            f"- Both correct: {audit['paired_outcomes']['both_correct']}.",
            f"- Low only correct: {audit['paired_outcomes']['low_only_correct']}.",
            f"- None only correct: {audit['paired_outcomes']['none_only_correct']}.",
            f"- Both wrong: {audit['paired_outcomes']['both_wrong']}.",
            f"- Both postal-code substitutions were missed by both configurations: "
            f"{observations['postal_code_substitution']['both_wrong']}/"
            f"{observations['postal_code_substitution']['exposures']}.",
            f"- Terra-low's {observations['wbs_misses']} WBS misses span "
            f"{observations['distinct_missed_wbs_subtypes']} corruption subtypes.",
            f"- Caution: {observations['small_subgroup_caution']}",
            "",
            "## Prompt assessment",
            "",
            f"The prompt may contribute: {hypothesis['reason']} However, the audit "
            "does not support one narrow Terra-specific prompt change. "
            f"{hypothesis['reason_not_supported']}",
            "",
            "## Decision",
            "",
            "Stop Terra on this screen. Do not tune or rerun Terra against these "
            "48 cases. The next experiment is a predeclared, fresh Sol screen "
            "whose cases do not overlap this development screen.",
            "",
        ]
    )
    return "\n".join(rows)


def write_terra_effort_failure_audit(
    *,
    input_path: Path = INPUT_PATH,
    truth_path: Path = TRUTH_PATH,
    none_predictions_path: Path = NONE_RUN_DIR / "predictions.jsonl",
    low_predictions_path: Path = LOW_RUN_DIR / "predictions.jsonl",
    output_dir: Path = COMPARISON_DIR,
) -> dict[str, Path]:
    audit = build_terra_effort_failure_audit(
        input_rows=load_jsonl(input_path),
        truth_rows=load_jsonl(truth_path),
        none_rows=load_jsonl(none_predictions_path),
        low_rows=load_jsonl(low_predictions_path),
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "failure_audit.json"
    markdown_path = output_dir / "failure_audit.md"
    json_path.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_markdown(audit), encoding="utf-8")
    return {"json": json_path, "markdown": markdown_path}


def main() -> None:
    written = write_terra_effort_failure_audit()
    print(
        json.dumps(
            {name: str(path) for name, path in written.items()},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
