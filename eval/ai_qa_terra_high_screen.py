from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from eval.ai_qa_clean_generator import generate_clean_ai_qa_cases
from eval.ai_qa_datasets import (
    build_ai_qa_split_from_clean_cases,
    verify_ai_qa_split_rows,
)
from eval.ai_qa_luna_v5_cycle import (
    LUNA_V5_WBS_PHRASES,
    _replace_wbs_semantics,
)
from eval.ai_qa_scorer import TRUTH_FIELD_TO_ERROR_FIELD
from eval.ai_qa_terra_effort_screen import (
    _canonical_json,
    _derived_seed,
    _read_jsonl,
    _sha256_file,
    _signature,
)
from eval.ai_qa_terra_v2_screen import (
    DEFAULT_TERRA_V2_SCREEN_DIR,
    _prior_input_paths,
)


SCHEMA_VERSION = "1.0"
SCREEN_SEED = 20260823
SCREEN_SPLIT = "terra_high_reasoning_screen"
DEFAULT_TERRA_HIGH_SCREEN_DIR = (
    Path(__file__).with_name("datasets") / SCREEN_SPLIT
)
MODEL_INPUTS_FILE = "model_inputs.jsonl"
TRUTH_FILE = "truth.jsonl"

COUNTS = {"clean": 12, "corrupted": 36}
ERROR_DISTRIBUTION = {
    "wbs": 14,
    "rooms": 14,
    "rent_kalt": 2,
    "district": 2,
    "address_postal_code": 2,
    "floor": 1,
    "rent_warm": 1,
}

CLEAN_FAMILIES = (
    "No WBS required",
    "No WBS required",
    "WBS required, type unknown",
    "WBS required, type unknown",
    "100",
    "100",
    "100, 140",
    "100, 140",
    "160, 180, 220",
    "160, 180, 220",
    "140, 160, 180, 220",
    "100, 140, 160, 180",
)
WBS_ERROR_FAMILIES = (
    "No WBS required",
    "No WBS required",
    "WBS required, type unknown",
    "WBS required, type unknown",
    "100",
    "100",
    "100, 140",
    "100, 140",
    "160, 180, 220",
    "160, 180, 220",
    "140, 160, 180, 220",
    "140, 160, 180, 220",
    "100, 140, 160, 180",
    "100, 140, 160, 180",
)
NON_WBS_ERROR_FAMILIES = (
    "No WBS required",
    "No WBS required",
    "No WBS required",
    "WBS required, type unknown",
    "WBS required, type unknown",
    "WBS required, type unknown",
    "100",
    "100",
    "100",
    "100, 140",
    "100, 140",
    "100, 140",
    "160, 180, 220",
    "160, 180, 220",
    "160, 180, 220",
    "160, 180, 220",
    "140, 160, 180, 220",
    "140, 160, 180, 220",
    "140, 160, 180, 220",
    "100, 140, 160, 180",
    "100, 140, 160, 180",
    "100, 140, 160, 180",
)


def _corruption_fields(seed: int) -> list[str]:
    fields = [
        field
        for field, count in ERROR_DISTRIBUTION.items()
        for _ in range(count)
    ]
    random.Random(_derived_seed(seed, "custom-field-order")).shuffle(fields)
    return fields


def _family_order(seed: int) -> list[str]:
    clean = list(CLEAN_FAMILIES)
    wbs = list(WBS_ERROR_FAMILIES)
    non_wbs = list(NON_WBS_ERROR_FAMILIES)
    random.Random(_derived_seed(seed, "terra-high-clean-families")).shuffle(clean)
    random.Random(_derived_seed(seed, "terra-high-wbs-families")).shuffle(wbs)
    random.Random(_derived_seed(seed, "terra-high-non-wbs-families")).shuffle(
        non_wbs
    )
    corrupted: list[str] = []
    wbs_index = 0
    non_wbs_index = 0
    for field in _corruption_fields(seed):
        if field == "wbs":
            corrupted.append(wbs[wbs_index])
            wbs_index += 1
        else:
            corrupted.append(non_wbs[non_wbs_index])
            non_wbs_index += 1
    return [*clean, *corrupted]


def build_terra_high_screen_rows(
    *,
    seed: int = SCREEN_SEED,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    families = _family_order(seed)
    source_cases = generate_clean_ai_qa_cases(
        count=len(families),
        seed=_derived_seed(seed, "terra-high-source-cases"),
    )
    occurrences: Counter[str] = Counter()
    specialized = []
    for case, family in zip(source_cases, families):
        phrases = LUNA_V5_WBS_PHRASES[family]
        offset = _derived_seed(seed, f"terra-high-phrase:{family}") % len(phrases)
        phrase = phrases[(offset + occurrences[family]) % len(phrases)]
        occurrences[family] += 1
        specialized.append(
            _replace_wbs_semantics(
                case,
                expected_wbs=family,
                phrase=phrase,
            )
        )
    rows = build_ai_qa_split_from_clean_cases(
        source_cases=specialized,
        seed=seed,
        counts=COUNTS,
        error_distribution=ERROR_DISTRIBUTION,
    )
    verify_ai_qa_split_rows(
        split_name=SCREEN_SPLIT,
        input_rows=rows[0],
        truth_rows=rows[1],
        expected_counts=COUNTS,
        expected_distribution=ERROR_DISTRIBUTION,
    )
    _verify_composition(*rows)
    return rows


def _find_family(raw_text: str) -> str:
    matches = [
        family
        for family, phrases in LUNA_V5_WBS_PHRASES.items()
        for phrase in phrases
        if raw_text.endswith(phrase)
    ]
    if len(matches) != 1:
        raise ValueError("Terra high screen row lacks one registered WBS phrase")
    return matches[0]


def _verify_composition(
    input_rows: Sequence[Mapping[str, object]],
    truth_rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    clean_families: Counter[str] = Counter()
    wbs_families: Counter[str] = Counter()
    non_wbs_families: Counter[str] = Counter()
    non_wbs_fields: Counter[str] = Counter()
    for input_row, truth_row in zip(input_rows, truth_rows):
        if input_row["case_id"] != truth_row["case_id"]:
            raise ValueError("Terra high screen input/truth order mismatch")
        family = _find_family(str(input_row["raw_text"]))
        if truth_row["case_type"] == "clean":
            clean_families[family] += 1
            continue
        field = TRUTH_FIELD_TO_ERROR_FIELD[str(truth_row["corrupted_field"])]
        if field == "wbs":
            wbs_families[family] += 1
        else:
            non_wbs_families[family] += 1
            non_wbs_fields[field] += 1
    if clean_families != Counter(CLEAN_FAMILIES):
        raise ValueError("Terra high screen clean WBS composition mismatch")
    if wbs_families != Counter(WBS_ERROR_FAMILIES):
        raise ValueError("Terra high screen WBS-error composition mismatch")
    if non_wbs_families != Counter(NON_WBS_ERROR_FAMILIES):
        raise ValueError("Terra high screen non-WBS composition mismatch")
    expected_non_wbs = Counter(
        field
        for field, count in ERROR_DISTRIBUTION.items()
        if field != "wbs"
        for _ in range(count)
    )
    if non_wbs_fields != expected_non_wbs:
        raise ValueError("Terra high screen non-WBS field composition mismatch")
    return {
        "clean_families": dict(sorted(clean_families.items())),
        "wbs_error_families": dict(sorted(wbs_families.items())),
        "non_wbs_error_families": dict(sorted(non_wbs_families.items())),
        "non_wbs_error_fields": dict(sorted(non_wbs_fields.items())),
    }


def _prior_paths() -> list[Path]:
    return [
        *_prior_input_paths(),
        DEFAULT_TERRA_V2_SCREEN_DIR / MODEL_INPUTS_FILE,
    ]


def _verify_isolation(
    input_rows: Sequence[Mapping[str, object]],
) -> dict[str, int]:
    current = {_signature(row) for row in input_rows}
    overlaps = {
        f"{path.parent.name}_{path.stem}": len(
            current & {_signature(row) for row in _read_jsonl(path)}
        )
        for path in _prior_paths()
    }
    if any(overlaps.values()):
        raise ValueError(f"Terra high screen overlaps prior data: {overlaps}")
    return overlaps


def _write_jsonl(
    path: Path,
    rows: Sequence[Mapping[str, object]],
) -> None:
    path.write_text(
        "".join(f"{_canonical_json(row)}\n" for row in rows),
        encoding="utf-8",
    )


def write_terra_high_screen(
    output_dir: Path = DEFAULT_TERRA_HIGH_SCREEN_DIR,
) -> dict[str, object]:
    if any(
        (output_dir / name).exists()
        for name in (MODEL_INPUTS_FILE, TRUTH_FILE, "dataset_manifest.json")
    ):
        raise FileExistsError("Terra high screen artifacts already exist")
    inputs, truth = build_terra_high_screen_rows()
    overlaps = _verify_isolation(inputs)
    output_dir.mkdir(parents=True, exist_ok=True)
    input_path = output_dir / MODEL_INPUTS_FILE
    truth_path = output_dir / TRUTH_FILE
    _write_jsonl(input_path, inputs)
    _write_jsonl(truth_path, truth)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "experiment": "synthetic offline Terra medium-vs-high reasoning screen",
        "hypothesis": (
            "Higher reasoning improves direct comparison accuracy with the "
            "frozen terra-v1 prompt and no category regression."
        ),
        "seed": SCREEN_SEED,
        "split": SCREEN_SPLIT,
        "counts": {**COUNTS, "total": sum(COUNTS.values())},
        "error_distribution": ERROR_DISTRIBUTION,
        "composition": _verify_composition(inputs, truth),
        "model_inputs": {
            "file": input_path.name,
            "lines": len(inputs),
            "sha256": _sha256_file(input_path),
        },
        "truth": {
            "file": truth_path.name,
            "lines": len(truth),
            "sha256": _sha256_file(truth_path),
        },
        "isolation": {
            "comparison_basis": "raw_text plus parser_snapshot",
            "overlaps": overlaps,
        },
        "profiles": [
            {
                "id": "terra-v1-medium",
                "model": "gpt-5.6-terra",
                "prompt_version": "terra-v1",
                "reasoning_effort": "medium",
            },
            {
                "id": "terra-v1-high",
                "model": "gpt-5.6-terra",
                "prompt_version": "terra-v1",
                "reasoning_effort": "high",
            },
        ],
        "advancement_rule": {
            "absolute": {
                "coverage": 1.0,
                "technical_failures": 0,
                "minimum_correct_rooms": 13,
                "minimum_correct_wbs": 13,
                "maximum_clean_false_alerts": 1,
                "minimum_correct_other_fields": 7,
                "minimum_total_correct": 45,
            },
            "comparative": {
                "minimum_total_gain_vs_medium": 1,
                "minimum_matching_critical_gain_vs_medium": 1,
                "wbs_regressions_allowed": 0,
                "rooms_regressions_allowed": 0,
                "clean_false_alert_regressions_allowed": 0,
                "other_field_regressions_allowed": 0,
            },
        },
        "boundaries": {
            "development_only": True,
            "calibration_or_validation_evidence": False,
            "consumed_validation_reused": False,
            "locked_holdout_used": False,
            "openai_called_during_generation": False,
            "product_runtime_modified": False,
            "sol_authorized": False,
        },
    }
    manifest_path = output_dir / "dataset_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    verify_terra_high_screen(output_dir)
    return manifest


def verify_terra_high_screen(
    output_dir: Path = DEFAULT_TERRA_HIGH_SCREEN_DIR,
) -> dict[str, Any]:
    manifest = json.loads(
        (output_dir / "dataset_manifest.json").read_text(encoding="utf-8")
    )
    input_path = output_dir / str(manifest["model_inputs"]["file"])
    truth_path = output_dir / str(manifest["truth"]["file"])
    if _sha256_file(input_path) != manifest["model_inputs"]["sha256"]:
        raise ValueError("Terra high screen input hash mismatch")
    if _sha256_file(truth_path) != manifest["truth"]["sha256"]:
        raise ValueError("Terra high screen truth hash mismatch")
    inputs, truth = _read_jsonl(input_path), _read_jsonl(truth_path)
    verify_ai_qa_split_rows(
        split_name=SCREEN_SPLIT,
        input_rows=inputs,
        truth_rows=truth,
        expected_counts=COUNTS,
        expected_distribution=ERROR_DISTRIBUTION,
    )
    if _verify_composition(inputs, truth) != manifest["composition"]:
        raise ValueError("Terra high screen composition metadata mismatch")
    if _verify_isolation(inputs) != manifest["isolation"]["overlaps"]:
        raise ValueError("Terra high screen isolation metadata mismatch")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate the independent Terra medium-vs-high screen.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_TERRA_HIGH_SCREEN_DIR,
    )
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    manifest = (
        verify_terra_high_screen(args.output_dir)
        if args.verify_only
        else write_terra_high_screen(args.output_dir)
    )
    print(
        json.dumps(
            {
                "seed": manifest["seed"],
                "counts": manifest["counts"],
                "error_distribution": manifest["error_distribution"],
                "model_inputs_sha256": manifest["model_inputs"]["sha256"],
                "truth_sha256": manifest["truth"]["sha256"],
                "overlaps": manifest["isolation"]["overlaps"],
                "profiles": manifest["profiles"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
