from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from eval.ai_qa_luna_v4_audit import _find_wbs_phrase, _prediction_value
from eval.ai_qa_luna_v5_cycle import LUNA_V5_WBS_PHRASES
from eval.ai_qa_luna_low_cycle import DEFAULT_LUNA_LOW_DATASET_DIR
from eval.ai_qa_scorer import TRUTH_FIELD_TO_ERROR_FIELD, load_jsonl


RUN_DIR = Path(__file__).with_name("runs") / "luna-low-calibration"
INPUT_PATH = DEFAULT_LUNA_LOW_DATASET_DIR / "calibration_model_inputs.jsonl"
TRUTH_PATH = DEFAULT_LUNA_LOW_DATASET_DIR / "calibration_truth.jsonl"
PREDICTIONS_PATH = RUN_DIR / "predictions.jsonl"
PREVIOUS_AUDIT_PATH = (
    Path(__file__).with_name("runs")
    / "luna-v5-calibration"
    / "failure_audit.json"
)
WBS_CORRUPTED_CASES = 56
WBS_GATE = 0.90


def _index_rows(
    rows: Sequence[Mapping[str, object]],
    *,
    label: str,
) -> dict[str, Mapping[str, object]]:
    indexed = {str(row["case_id"]): row for row in rows}
    if len(indexed) != len(rows):
        raise ValueError(f"{label} contains duplicate case IDs")
    return indexed


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _counter_rows(
    exposures: Counter[str],
    misses: Counter[str],
    *,
    key_name: str,
) -> list[dict[str, object]]:
    return [
        {
            key_name: key,
            "exposures": exposures[key],
            "misses": misses[key],
            "correctly_localized": exposures[key] - misses[key],
            "localized_recall": _rate(
                exposures[key] - misses[key],
                exposures[key],
            ),
        }
        for key in sorted(
            exposures,
            key=lambda value: (misses[value], exposures[value], value),
            reverse=True,
        )
    ]


def build_luna_low_failure_audit(
    *,
    input_rows: Sequence[Mapping[str, object]],
    truth_rows: Sequence[Mapping[str, object]],
    prediction_rows: Sequence[Mapping[str, object]],
    previous_audit: Mapping[str, object] | None = None,
) -> dict[str, object]:
    truth_by_id = _index_rows(truth_rows, label="truth")
    prediction_by_id = _index_rows(prediction_rows, label="predictions")
    input_ids = {str(row["case_id"]) for row in input_rows}
    if input_ids != set(truth_by_id) or input_ids != set(prediction_by_id):
        raise ValueError("input, truth, and prediction case IDs differ")

    totals: Counter[str] = Counter()
    field_exposures: Counter[str] = Counter()
    field_misses: Counter[str] = Counter()
    wbs_family_exposures: Counter[str] = Counter()
    wbs_family_misses: Counter[str] = Counter()
    wbs_type_exposures: Counter[str] = Counter()
    wbs_type_misses: Counter[str] = Counter()
    wbs_transition_exposures: Counter[str] = Counter()
    wbs_transition_misses: Counter[str] = Counter()

    for input_row in input_rows:
        case_id = str(input_row["case_id"])
        truth = truth_by_id[case_id]
        has_error, predicted_field = _prediction_value(
            prediction_by_id[case_id]
        )
        case_type = truth.get("case_type")
        if case_type == "clean":
            totals["clean_cases"] += 1
            if has_error:
                totals["false_alerts"] += 1
            continue
        corrupted_field = truth.get("corrupted_field")
        if case_type != "corrupted" or not isinstance(corrupted_field, str):
            raise ValueError("truth case has invalid type or corrupted field")
        try:
            expected_field = TRUTH_FIELD_TO_ERROR_FIELD[corrupted_field]
        except KeyError:
            raise ValueError("truth case has an unsupported corrupted field") from None

        totals["corrupted_cases"] += 1
        field_exposures[expected_field] += 1
        localized = has_error and predicted_field == expected_field
        if not has_error:
            totals["false_negatives"] += 1
        elif not localized:
            totals["wrong_field_localizations"] += 1
        if not localized:
            field_misses[expected_field] += 1

        if expected_field != "wbs":
            continue
        _phrase, family = _find_wbs_phrase(
            str(input_row["raw_text"]),
            wbs_phrases=LUNA_V5_WBS_PHRASES,
        )
        corruption_type = truth.get("corruption_type")
        if not isinstance(corruption_type, str):
            raise ValueError("WBS truth row lacks corruption_type")
        transition = (
            f"{truth.get('expected_value')} -> {truth.get('corrupted_value')}"
        )
        wbs_family_exposures[family] += 1
        wbs_type_exposures[corruption_type] += 1
        wbs_transition_exposures[transition] += 1
        if not localized:
            wbs_family_misses[family] += 1
            wbs_type_misses[corruption_type] += 1
            wbs_transition_misses[transition] += 1

    correctly_localized_wbs = (
        field_exposures["wbs"] - field_misses["wbs"]
    )
    minimum_correct = int(WBS_CORRUPTED_CASES * WBS_GATE + 0.999999)
    normalized_totals = {
        key: totals[key]
        for key in (
            "clean_cases",
            "corrupted_cases",
            "false_negatives",
            "false_alerts",
            "wrong_field_localizations",
        )
    }
    field_rows = _counter_rows(
        field_exposures,
        field_misses,
        key_name="field",
    )
    family_rows = _counter_rows(
        wbs_family_exposures,
        wbs_family_misses,
        key_name="semantic_family",
    )
    type_rows = _counter_rows(
        wbs_type_exposures,
        wbs_type_misses,
        key_name="corruption_type",
    )
    missed_transition_rows = [
        row
        for row in _counter_rows(
            wbs_transition_exposures,
            wbs_transition_misses,
            key_name="transition",
        )
        if int(row["misses"]) > 0
    ]
    no_or_generic_misses = sum(
        wbs_family_misses[family]
        for family in ("No WBS required", "WBS required, type unknown")
    )
    zero_miss_families = sorted(
        family
        for family in wbs_family_exposures
        if wbs_family_misses[family] == 0
    )
    cross_cycle: dict[str, object] | None = None
    if previous_audit is not None:
        previous_totals = previous_audit.get("totals")
        if not isinstance(previous_totals, Mapping):
            raise ValueError("previous audit lacks totals")
        cross_cycle = {
            "comparison_type": (
                "descriptive only; different calibration inputs and reasoning "
                "configurations, not a paired causal estimate"
            ),
            "previous_cycle": "Luna-v5 none",
            "current_cycle": "Luna-v5 low",
            "wbs_localized_misses": {
                "previous": int(previous_totals.get("wbs_localized_misses", 0)),
                "current": field_misses["wbs"],
                "denominator_each": WBS_CORRUPTED_CASES,
            },
            "clean_false_alerts": {
                "previous": int(previous_totals.get("false_alerts", 0)),
                "current": totals["false_alerts"],
                "denominator_each": 140,
            },
            "wrong_field_localizations": {
                "previous": int(
                    previous_totals.get("wrong_field_localizations", 0)
                ),
                "current": totals["wrong_field_localizations"],
            },
        }

    return {
        "experiment": "synthetic offline AI QA Luna-low failure audit",
        "scope": (
            "aggregate calibration diagnostics only; no validation or locked "
            "holdout inference"
        ),
        "configuration": {
            "model": "gpt-5.6-luna",
            "reasoning_effort": "low",
            "prompt_version": "luna-v5",
        },
        "totals": normalized_totals,
        "field_outcomes": field_rows,
        "wbs_gate": {
            "threshold": WBS_GATE,
            "corrupted_cases": field_exposures["wbs"],
            "correctly_localized": correctly_localized_wbs,
            "minimum_correct_to_pass": minimum_correct,
            "shortfall_cases": max(0, minimum_correct - correctly_localized_wbs),
            "status": (
                "pass" if correctly_localized_wbs >= minimum_correct else "fail"
            ),
        },
        "wbs_by_semantic_family": family_rows,
        "wbs_by_corruption_type": type_rows,
        "missed_wbs_transitions": missed_transition_rows,
        "aggregate_observations": {
            "no_or_generic_wbs_family_misses": no_or_generic_misses,
            "total_wbs_misses": field_misses["wbs"],
            "distinct_missed_transitions": len(missed_transition_rows),
            "maximum_misses_in_one_transition": max(
                (int(row["misses"]) for row in missed_transition_rows),
                default=0,
            ),
            "zero_miss_semantic_families": zero_miss_families,
            "small_subgroup_caution": (
                "Subtype and family counts are diagnostic calibration slices, "
                "not independent performance estimates."
            ),
        },
        "cross_cycle_context": cross_cycle,
        "boundaries": {
            "contains_case_ids": False,
            "contains_raw_listing_text": False,
            "contains_parser_snapshots": False,
            "prompt_tuning_authorized": False,
            "calibration_rerun_authorized": False,
            "configuration_freeze_created": False,
            "validation_authorized": False,
            "locked_holdout_used": False,
            "new_model_calls": False,
        },
        "decision": {
            "calibration_status": "fail",
            "action": "stop_without_freeze_or_validation",
            "next_decision": (
                "close Luna with the measured limitation or separately authorize "
                "a stronger-model experiment on new data"
            ),
        },
    }


def _percent(value: object) -> str:
    return f"{float(value) * 100:.1f}%"


def render_markdown(audit: Mapping[str, object]) -> str:
    totals = audit["totals"]
    gate = audit["wbs_gate"]
    rows = [
        "# Luna-low Calibration Failure Audit",
        "",
        "Synthetic offline calibration diagnostics only. No validation, locked "
        "holdout, or new model call was used.",
        "",
        "## Outcome",
        "",
        f"- False negatives: {totals.get('false_negatives', 0)} of "
        f"{totals.get('corrupted_cases', 0)} corrupted cases.",
        f"- Clean false alerts: {totals.get('false_alerts', 0)} of "
        f"{totals.get('clean_cases', 0)} clean cases.",
        f"- Wrong field localizations: "
        f"{totals.get('wrong_field_localizations', 0)}.",
        f"- WBS: {gate['correctly_localized']}/{gate['corrupted_cases']}; "
        f"minimum {gate['minimum_correct_to_pass']} required; status **{gate['status']}**.",
        "",
        "## Misses by field",
        "",
        "| Field | Cases | Misses | Localized recall |",
        "|---|---:|---:|---:|",
    ]
    for row in audit["field_outcomes"]:
        rows.append(
            f"| {row['field']} | {row['exposures']} | {row['misses']} | "
            f"{_percent(row['localized_recall'])} |"
        )
    rows.extend(
        [
            "",
            "## WBS misses by semantic family",
            "",
            "| Expected normalized WBS | Cases | Misses | Localized recall |",
            "|---|---:|---:|---:|",
        ]
    )
    for row in audit["wbs_by_semantic_family"]:
        rows.append(
            f"| {row['semantic_family']} | {row['exposures']} | "
            f"{row['misses']} | {_percent(row['localized_recall'])} |"
        )
    rows.extend(
        [
            "",
            "## WBS misses by corruption subtype",
            "",
            "| Corruption subtype | Cases | Misses | Localized recall |",
            "|---|---:|---:|---:|",
        ]
    )
    for row in audit["wbs_by_corruption_type"]:
        rows.append(
            f"| {row['corruption_type']} | {row['exposures']} | "
            f"{row['misses']} | {_percent(row['localized_recall'])} |"
        )
    rows.extend(
        [
            "",
            "## Missed WBS transitions",
            "",
            "| Expected -> corrupted | Exposures | Misses |",
            "|---|---:|---:|",
        ]
    )
    for row in audit["missed_wbs_transitions"]:
        transition = str(row["transition"]).replace("|", "\\|")
        rows.append(
            f"| {transition} | {row['exposures']} | {row['misses']} |"
        )
    observations = audit["aggregate_observations"]
    zero_miss_families = ", ".join(
        f"`{family}`" for family in observations["zero_miss_semantic_families"]
    )
    rows.extend(
        [
            "",
            "## Aggregate pattern",
            "",
            f"- {observations['no_or_generic_wbs_family_misses']} of "
            f"{observations['total_wbs_misses']} WBS misses occurred in the "
            "`No WBS required` or generic `WBS required, type unknown` families.",
            f"- The {observations['distinct_missed_transitions']} WBS misses used "
            f"{observations['distinct_missed_transitions']} distinct transitions; "
            f"the maximum count for one transition was "
            f"{observations['maximum_misses_in_one_transition']}.",
            f"- Zero-miss WBS families: {zero_miss_families}.",
            f"- Caution: {observations['small_subgroup_caution']}",
        ]
    )
    comparison = audit.get("cross_cycle_context")
    if isinstance(comparison, Mapping):
        wbs = comparison["wbs_localized_misses"]
        false_alerts = comparison["clean_false_alerts"]
        wrong_fields = comparison["wrong_field_localizations"]
        rows.extend(
            [
                "",
                "## Cross-cycle context",
                "",
                "Different fresh calibration inputs were used, so this comparison "
                "is descriptive and must not be interpreted as a paired causal effect.",
                "",
                f"- WBS localized misses: {wbs['previous']}/56 with Luna-v5 none; "
                f"{wbs['current']}/56 with Luna-v5 low.",
                f"- Clean false alerts: {false_alerts['previous']}/140 with none; "
                f"{false_alerts['current']}/140 with low.",
                f"- Wrong field localizations: {wrong_fields['previous']} with none; "
                f"{wrong_fields['current']} with low.",
            ]
        )
    rows.extend(
        [
            "",
            "## Decision",
            "",
            "Calibration remains failed. Do not freeze the configuration, run "
            "validation, rerun calibration, or tune the prompt against these cases. "
            "The next decision is whether to close Luna with this measured limitation "
            "or authorize a separately predeclared stronger-model experiment using "
            "new data.",
            "",
        ]
    )
    return "\n".join(rows)


def write_luna_low_failure_audit(
    *,
    input_path: Path = INPUT_PATH,
    truth_path: Path = TRUTH_PATH,
    predictions_path: Path = PREDICTIONS_PATH,
    previous_audit_path: Path = PREVIOUS_AUDIT_PATH,
    output_dir: Path = RUN_DIR,
) -> dict[str, Path]:
    previous_audit = json.loads(previous_audit_path.read_text(encoding="utf-8"))
    audit = build_luna_low_failure_audit(
        input_rows=load_jsonl(input_path),
        truth_rows=load_jsonl(truth_path),
        prediction_rows=load_jsonl(predictions_path),
        previous_audit=previous_audit,
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
    written = write_luna_low_failure_audit()
    print(
        json.dumps(
            {name: str(path) for name, path in written.items()},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
