from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from eval.ai_qa_datasets import (
    ARTIFACT_FILENAMES,
    DEFAULT_DATASET_DIR,
    LOCKED_HOLDOUT_COUNTS,
    LOCKED_HOLDOUT_ERROR_DISTRIBUTION,
    verify_ai_qa_dataset,
)


READINESS_SCHEMA_VERSION = "1.0"
EVAL_ROOT = Path(__file__).resolve().parent
DATASETS_ROOT = EVAL_ROOT / "datasets"

_TRUTH_FIELD_TO_PRODUCT_FIELD = {
    "display_wbs": "WBS",
    "rent_kalt": "Kaltmiete",
    "rooms": "rooms",
    "address": "address/postal code",
    "postal_code": "address/postal code",
    "district": "district",
    "floor": "floor",
    "rent_warm": "Warmmiete",
}
_PRODUCT_FIELD_TO_SNAPSHOT_FIELD = {
    "WBS": "display_wbs",
    "Kaltmiete": "rent_kalt",
    "rooms": "rooms",
    "district": "district",
    "floor": "floor",
    "Warmmiete": "rent_warm",
}
_EXPECTED_FORMAT_FAMILIES = {
    "portal_lines",
    "compact_block",
    "prose_first",
    "costs_first",
    "sectioned",
    "label_table",
}
_EXPECTED_WBS_FAMILIES = {
    "No WBS required",
    "WBS required, type unknown",
    "100",
    "100, 140",
    "100, 140, 160, 180",
    "140, 160, 180, 220",
    "160, 180, 220",
}
_MATCHING_CRITICAL_FIELDS = ("WBS", "district", "Kaltmiete", "rooms")


class HoldoutReadinessError(ValueError):
    """Raised when the locked holdout no longer satisfies its frozen contract."""


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as artifact:
        for line_number, line in enumerate(artifact, start=1):
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise HoldoutReadinessError(
                    f"{path.name}:{line_number} is not valid JSON"
                ) from exc
            if not isinstance(value, dict):
                raise HoldoutReadinessError(
                    f"{path.name}:{line_number} must be an object"
                )
            rows.append(value)
    return rows


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _input_signature_hash(row: Mapping[str, object]) -> str:
    payload = {
        "raw_text": row["raw_text"],
        "parser_snapshot": row["parser_snapshot"],
    }
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _format_family(raw_text: str) -> str:
    if raw_text.startswith("Wohnungsangebot\n"):
        return "portal_lines"
    if " | Zimmer:" in raw_text and "Gesamtmiete:" in raw_text:
        return "compact_block"
    if raw_text.startswith("In "):
        return "prose_first"
    if raw_text.startswith("Mietkonditionen\n"):
        return "costs_first"
    if raw_text.startswith("LAGE UND ANSCHRIFT\n"):
        return "sectioned"
    if raw_text.startswith("Wohnlage      "):
        return "label_table"
    return "unknown"


def _expected_snapshot_value(
    *,
    snapshot: Mapping[str, object],
    truth_row: Mapping[str, object],
    snapshot_field: str,
) -> object:
    if truth_row["corrupted_field"] == snapshot_field:
        return truth_row["expected_value"]
    return snapshot[snapshot_field]


def _discover_prior_input_paths(
    *,
    dataset_dir: Path,
    datasets_root: Path = DATASETS_ROOT,
) -> list[Path]:
    locked_input = (
        dataset_dir / ARTIFACT_FILENAMES["locked_holdout_model_inputs"]
    ).resolve()
    return [
        path
        for path in sorted(datasets_root.rglob("*.jsonl"))
        if path.resolve() != locked_input
        and "truth" not in path.name
        and "model_inputs" in path.name
    ]


def _overlap_counts(
    *,
    holdout_inputs: Sequence[Mapping[str, object]],
    comparison_input_paths: Iterable[Path],
) -> dict[str, int]:
    holdout_signatures = {
        _input_signature_hash(row)
        for row in holdout_inputs
    }
    overlaps: dict[str, int] = {}
    for path in comparison_input_paths:
        rows = _read_jsonl(path)
        model_rows = [
            row
            for row in rows
            if "raw_text" in row and "parser_snapshot" in row
        ]
        comparison_signatures = {
            _input_signature_hash(row)
            for row in model_rows
        }
        try:
            label = str(path.relative_to(EVAL_ROOT.parent))
        except ValueError:
            label = str(path)
        overlaps[label] = len(holdout_signatures & comparison_signatures)
    return overlaps


def _minimum_successes(total: int, target: float) -> int:
    return math.ceil(total * target)


def _maximum_failures(total: int, target: float) -> int:
    return math.floor(total * target)


def _release_gates() -> dict[str, object]:
    clean = LOCKED_HOLDOUT_COUNTS["clean"]
    corrupted = LOCKED_HOLDOUT_COUNTS["corrupted"]
    total = clean + corrupted
    return {
        "product_scorecard": {
            "parser_error_detection_rate": {
                "target": ">= 95%",
                "minimum_count": _minimum_successes(corrupted, 0.95),
                "denominator": corrupted,
            },
            "false_alert_rate": {
                "target": "<= 3%",
                "maximum_count": _maximum_failures(clean, 0.03),
                "denominator": clean,
            },
            "correct_field_detection_rate": {
                "target": ">= 90%",
                "minimum_count": _minimum_successes(corrupted, 0.90),
                "denominator": corrupted,
            },
            "successful_check_rate": {
                "target": ">= 99.5%",
                "minimum_count": _minimum_successes(total, 0.995),
                "denominator": total,
            },
        },
        "matching_critical_fields": {
            field: {
                "target": ">= 90%",
                "minimum_count": _minimum_successes(
                    LOCKED_HOLDOUT_ERROR_DISTRIBUTION[
                        {
                            "WBS": "wbs",
                            "district": "district",
                            "Kaltmiete": "rent_kalt",
                            "rooms": "rooms",
                        }[field]
                    ],
                    0.90,
                ),
                "denominator": LOCKED_HOLDOUT_ERROR_DISTRIBUTION[
                    {
                        "WBS": "wbs",
                        "district": "district",
                        "Kaltmiete": "rent_kalt",
                        "rooms": "rooms",
                    }[field]
                ],
            }
            for field in _MATCHING_CRITICAL_FIELDS
        },
        "engineering_gates_unchanged": True,
        "all_gates_must_pass": True,
    }


def audit_locked_holdout_readiness(
    dataset_dir: Path = DEFAULT_DATASET_DIR,
    *,
    comparison_input_paths: Sequence[Path] | None = None,
) -> dict[str, object]:
    """Return an aggregate-only readiness audit without exposing cases."""

    manifest = verify_ai_qa_dataset(dataset_dir)
    input_path = (
        dataset_dir / ARTIFACT_FILENAMES["locked_holdout_model_inputs"]
    )
    truth_path = dataset_dir / ARTIFACT_FILENAMES["locked_holdout_truth"]
    inputs = _read_jsonl(input_path)
    truth = _read_jsonl(truth_path)
    truth_by_id = {row["case_id"]: row for row in truth}

    case_types: Counter[str] = Counter()
    fields: Counter[str] = Counter()
    corruption_types: dict[str, Counter[str]] = defaultdict(Counter)
    formats: Counter[str] = Counter()
    formats_by_case_type: dict[str, Counter[str]] = defaultdict(Counter)
    expected_wbs: Counter[str] = Counter()
    wbs_error_families: Counter[str] = Counter()
    districts: Counter[str] = Counter()
    rooms: Counter[str] = Counter()
    floors: Counter[str] = Counter()

    for input_row in inputs:
        truth_row = truth_by_id[input_row["case_id"]]
        case_type = str(truth_row["case_type"])
        snapshot = input_row["parser_snapshot"]
        if not isinstance(snapshot, dict):
            raise HoldoutReadinessError("parser_snapshot must be an object")

        case_types[case_type] += 1
        family = _format_family(str(input_row["raw_text"]))
        formats[family] += 1
        formats_by_case_type[case_type][family] += 1

        wbs_value = _expected_snapshot_value(
            snapshot=snapshot,
            truth_row=truth_row,
            snapshot_field="display_wbs",
        )
        expected_wbs[str(wbs_value)] += 1
        districts[str(
            _expected_snapshot_value(
                snapshot=snapshot,
                truth_row=truth_row,
                snapshot_field="district",
            )
        )] += 1
        rooms[str(
            _expected_snapshot_value(
                snapshot=snapshot,
                truth_row=truth_row,
                snapshot_field="rooms",
            )
        )] += 1
        floors[str(
            _expected_snapshot_value(
                snapshot=snapshot,
                truth_row=truth_row,
                snapshot_field="floor",
            )
        )] += 1

        if case_type != "corrupted":
            continue
        truth_field = str(truth_row["corrupted_field"])
        product_field = _TRUTH_FIELD_TO_PRODUCT_FIELD[truth_field]
        fields[product_field] += 1
        corruption_types[product_field][
            str(truth_row["corruption_type"])
        ] += 1
        if truth_field == "display_wbs":
            wbs_error_families[str(truth_row["expected_value"])] += 1

    paths = (
        list(comparison_input_paths)
        if comparison_input_paths is not None
        else _discover_prior_input_paths(dataset_dir=dataset_dir)
    )
    overlaps = _overlap_counts(
        holdout_inputs=inputs,
        comparison_input_paths=paths,
    )
    signature_count = len({_input_signature_hash(row) for row in inputs})

    checks = {
        "manifest_and_hashes_valid": True,
        "case_counts_match": dict(case_types)
        == dict(LOCKED_HOLDOUT_COUNTS),
        "error_distribution_matches": dict(fields)
        == {
            "WBS": 75,
            "Kaltmiete": 60,
            "rooms": 50,
            "address/postal code": 40,
            "district": 30,
            "floor": 25,
            "Warmmiete": 20,
        },
        "all_exact_inputs_unique": signature_count == len(inputs),
        "all_six_format_families_present": set(formats)
        == _EXPECTED_FORMAT_FAMILIES,
        "clean_and_corrupted_format_comparable": all(
            49 <= formats_by_case_type[case_type][family] <= 51
            for case_type in ("clean", "corrupted")
            for family in _EXPECTED_FORMAT_FAMILIES
        ),
        "all_seven_wbs_families_present": set(expected_wbs)
        == _EXPECTED_WBS_FAMILIES,
        "every_wbs_family_has_corrupted_cases": set(wbs_error_families)
        == _EXPECTED_WBS_FAMILIES,
        "all_twelve_districts_present": len(districts) == 12,
        "all_eight_room_values_present": len(rooms) == 8,
        "all_ten_floor_values_present": len(floors) == 10,
        "zero_overlap_with_prior_inputs": not any(overlaps.values()),
    }
    ready = all(checks.values())
    if not ready:
        failed = [name for name, passed in checks.items() if not passed]
        raise HoldoutReadinessError(
            f"locked holdout readiness checks failed: {failed}"
        )

    return {
        "schema_version": READINESS_SCHEMA_VERSION,
        "status": "ready_with_declared_limitations",
        "suitable_for": (
            "one final synthetic offline capability test of the frozen "
            "Terra-high configuration"
        ),
        "not_suitable_for": (
            "production accuracy, natural parser-error prevalence, source "
            "coverage, or user-outcome claims"
        ),
        "source": {
            "dataset_manifest_sha256": hashlib.sha256(
                (
                    dataset_dir / ARTIFACT_FILENAMES["manifest"]
                ).read_bytes()
            ).hexdigest(),
            "model_inputs_sha256": manifest["splits"]["locked_holdout"][
                "artifacts"
            ]["model_inputs"]["sha256"],
            "truth_sha256": manifest["splits"]["locked_holdout"][
                "artifacts"
            ]["truth"]["sha256"],
        },
        "composition": {
            "case_types": dict(sorted(case_types.items())),
            "error_fields": dict(sorted(fields.items())),
            "corruption_types": {
                field: dict(sorted(counts.items()))
                for field, counts in sorted(corruption_types.items())
            },
            "format_families": dict(sorted(formats.items())),
            "format_families_by_case_type": {
                case_type: dict(sorted(counts.items()))
                for case_type, counts in sorted(
                    formats_by_case_type.items()
                )
            },
            "expected_wbs_families": dict(sorted(expected_wbs.items())),
            "wbs_error_families": dict(
                sorted(wbs_error_families.items())
            ),
            "district_count": len(districts),
            "room_value_count": len(rooms),
            "floor_value_count": len(floors),
            "unique_exact_inputs": signature_count,
        },
        "isolation": {
            "comparison_artifact_count": len(overlaps),
            "overlaps": dict(sorted(overlaps.items())),
        },
        "release_gates": _release_gates(),
        "checks": checks,
        "limitations": [
            (
                "The challenge set is balanced 300/300; this does not estimate "
                "real parser-error prevalence or production precision."
            ),
            (
                "Every corrupted case contains exactly one planted error; the "
                "set does not test multi-error listings, missing listings, or "
                "a complete parser collapse."
            ),
            (
                "Cases use six synthetic format templates from the same base "
                "generator family as the original development set. Exact "
                "inputs are independent, but generator-level transfer to real "
                "provider formats remains unmeasured."
            ),
            (
                "Clean and corrupted pools are comparable by aggregate format "
                "and field distributions, but they are not one-to-one paired "
                "versions of the same underlying listing."
            ),
            (
                "All seven WBS families are represented, but the 75 WBS "
                "corruptions are not evenly allocated across those families. "
                "The balanced Terra-high validation remains the stronger "
                "family-by-family WBS diagnostic."
            ),
        ],
        "decision": {
            "keep_existing_600_cases_frozen": True,
            "regenerate_or_rebalance_after_model_selection": False,
            "prompt_or_model_change_allowed_before_run": False,
            "one_run_only": True,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit locked-holdout fitness without exposing cases.",
    )
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=DEFAULT_DATASET_DIR,
    )
    args = parser.parse_args()
    audit = audit_locked_holdout_readiness(args.dataset_dir)
    print(json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
