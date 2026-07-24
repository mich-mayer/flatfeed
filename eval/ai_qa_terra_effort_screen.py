from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from eval.ai_qa_clean_generator import generate_clean_ai_qa_cases
from eval.ai_qa_datasets import (
    ARTIFACT_FILENAMES,
    DEFAULT_DATASET_DIR,
    build_ai_qa_split_from_clean_cases,
    verify_ai_qa_split_rows,
)
from eval.ai_qa_luna_calibration import DEFAULT_LUNA_DATASET_DIR
from eval.ai_qa_luna_effort_screen import DEFAULT_LUNA_EFFORT_SCREEN_DIR
from eval.ai_qa_luna_low_cycle import DEFAULT_LUNA_LOW_DATASET_DIR
from eval.ai_qa_luna_v3_cycle import DEFAULT_LUNA_V3_DATASET_DIR
from eval.ai_qa_luna_v4_cycle import DEFAULT_LUNA_V4_DATASET_DIR
from eval.ai_qa_luna_v5_cycle import (
    DEFAULT_LUNA_V5_DATASET_DIR,
    LUNA_V5_WBS_PHRASES,
    _replace_wbs_semantics,
)
from eval.ai_qa_scorer import TRUTH_FIELD_TO_ERROR_FIELD


SCREEN_SCHEMA_VERSION = "1.0"
SCREEN_SEED = 20260803
DEFAULT_TERRA_EFFORT_SCREEN_DIR = (
    Path(__file__).with_name("datasets") / "terra_effort_screen"
)
SCREEN_COUNTS = {"clean": 16, "corrupted": 32}
SCREEN_ERROR_DISTRIBUTION = {
    "wbs": 20,
    "rent_kalt": 2,
    "rooms": 2,
    "address_postal_code": 2,
    "district": 2,
    "floor": 2,
    "rent_warm": 2,
}
SCREEN_SPLIT = "terra_effort_screen"
SCREEN_MODEL_INPUTS = "model_inputs.jsonl"
SCREEN_TRUTH = "truth.jsonl"

CLEAN_FAMILIES = (
    "No WBS required",
    "No WBS required",
    "No WBS required",
    "WBS required, type unknown",
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
WBS_ERROR_FAMILIES = (
    "No WBS required",
    "No WBS required",
    "No WBS required",
    "No WBS required",
    "WBS required, type unknown",
    "WBS required, type unknown",
    "WBS required, type unknown",
    "WBS required, type unknown",
    "100",
    "100",
    "100",
    "100, 140",
    "100, 140",
    "100, 140",
    "100, 140, 160, 180",
    "100, 140, 160, 180",
    "160, 180, 220",
    "160, 180, 220",
    "140, 160, 180, 220",
    "140, 160, 180, 220",
)
NON_WBS_ERROR_FAMILIES = (
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


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _derived_seed(seed: int, namespace: str) -> int:
    return int.from_bytes(
        hashlib.sha256(f"{seed}:{namespace}".encode("utf-8")).digest()[:8],
        "big",
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as artifact:
        for chunk in iter(lambda: artifact.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, object]]) -> None:
    path.write_text(
        "".join(f"{_canonical_json(row)}\n" for row in rows),
        encoding="utf-8",
    )


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
    ]


def _signature(row: Mapping[str, object]) -> str:
    return _canonical_json(
        {"raw_text": row["raw_text"], "parser_snapshot": row["parser_snapshot"]}
    )


def _corruption_fields(seed: int) -> list[str]:
    fields = [
        field
        for field, count in SCREEN_ERROR_DISTRIBUTION.items()
        for _ in range(count)
    ]
    random.Random(_derived_seed(seed, "custom-field-order")).shuffle(fields)
    return fields


def _family_order(seed: int) -> list[str]:
    clean = list(CLEAN_FAMILIES)
    wbs = list(WBS_ERROR_FAMILIES)
    non_wbs = list(NON_WBS_ERROR_FAMILIES)
    random.Random(_derived_seed(seed, "terra-clean-families")).shuffle(clean)
    random.Random(_derived_seed(seed, "terra-wbs-families")).shuffle(wbs)
    random.Random(_derived_seed(seed, "terra-non-wbs-families")).shuffle(non_wbs)
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


def _find_family(raw_text: str) -> str:
    matches = [
        family
        for family, phrases in LUNA_V5_WBS_PHRASES.items()
        for phrase in phrases
        if raw_text.endswith(phrase)
    ]
    if len(matches) != 1:
        raise ValueError("Terra screen row lacks one registered WBS phrase")
    return matches[0]


def build_terra_effort_screen_rows(
    *,
    seed: int = SCREEN_SEED,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    families = _family_order(seed)
    source_cases = generate_clean_ai_qa_cases(
        count=len(families),
        seed=_derived_seed(seed, "terra-clean-source-cases"),
    )
    occurrences: Counter[str] = Counter()
    specialized = []
    for case, family in zip(source_cases, families):
        phrases = LUNA_V5_WBS_PHRASES[family]
        offset = _derived_seed(seed, f"terra-phrase:{family}") % len(phrases)
        phrase = phrases[(offset + occurrences[family]) % len(phrases)]
        occurrences[family] += 1
        specialized.append(
            _replace_wbs_semantics(
                case,
                expected_wbs=family,
                phrase=phrase,
            )
        )
    input_rows, truth_rows = build_ai_qa_split_from_clean_cases(
        source_cases=specialized,
        seed=seed,
        counts=SCREEN_COUNTS,
        error_distribution=SCREEN_ERROR_DISTRIBUTION,
    )
    verify_ai_qa_split_rows(
        split_name=SCREEN_SPLIT,
        input_rows=input_rows,
        truth_rows=truth_rows,
        expected_counts=SCREEN_COUNTS,
        expected_distribution=SCREEN_ERROR_DISTRIBUTION,
    )
    _verify_composition(input_rows, truth_rows)
    return input_rows, truth_rows


def _verify_composition(
    input_rows: Sequence[Mapping[str, object]],
    truth_rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    clean_families: Counter[str] = Counter()
    wbs_error_families: Counter[str] = Counter()
    non_wbs_fields: Counter[str] = Counter()
    for input_row, truth_row in zip(input_rows, truth_rows):
        if input_row["case_id"] != truth_row["case_id"]:
            raise ValueError("Terra screen input/truth order mismatch")
        family = _find_family(str(input_row["raw_text"]))
        if truth_row["case_type"] == "clean":
            clean_families[family] += 1
            continue
        expected = TRUTH_FIELD_TO_ERROR_FIELD[
            str(truth_row["corrupted_field"])
        ]
        if expected == "wbs":
            wbs_error_families[family] += 1
        else:
            non_wbs_fields[expected] += 1
    if clean_families != Counter(CLEAN_FAMILIES):
        raise ValueError("Terra screen clean WBS composition mismatch")
    if wbs_error_families != Counter(WBS_ERROR_FAMILIES):
        raise ValueError("Terra screen WBS-error composition mismatch")
    expected_non_wbs = Counter(
        field
        for field, count in SCREEN_ERROR_DISTRIBUTION.items()
        if field != "wbs"
        for _ in range(count)
    )
    if non_wbs_fields != expected_non_wbs:
        raise ValueError("Terra screen non-WBS composition mismatch")
    return {
        "clean_families": dict(sorted(clean_families.items())),
        "wbs_error_families": dict(sorted(wbs_error_families.items())),
        "non_wbs_error_fields": dict(sorted(non_wbs_fields.items())),
    }


def _prior_paths() -> list[Path]:
    return [
        DEFAULT_DATASET_DIR / ARTIFACT_FILENAMES["development_model_inputs"],
        DEFAULT_DATASET_DIR / ARTIFACT_FILENAMES["locked_holdout_model_inputs"],
        DEFAULT_LUNA_DATASET_DIR / "calibration_model_inputs.jsonl",
        DEFAULT_LUNA_DATASET_DIR / "validation_model_inputs.jsonl",
        DEFAULT_LUNA_V3_DATASET_DIR / "calibration_model_inputs.jsonl",
        DEFAULT_LUNA_V3_DATASET_DIR / "validation_model_inputs.jsonl",
        DEFAULT_LUNA_V4_DATASET_DIR / "calibration_model_inputs.jsonl",
        DEFAULT_LUNA_V4_DATASET_DIR / "validation_model_inputs.jsonl",
        DEFAULT_LUNA_V5_DATASET_DIR / "calibration_model_inputs.jsonl",
        DEFAULT_LUNA_V5_DATASET_DIR / "validation_model_inputs.jsonl",
        DEFAULT_LUNA_EFFORT_SCREEN_DIR / "model_inputs.jsonl",
        DEFAULT_LUNA_LOW_DATASET_DIR / "calibration_model_inputs.jsonl",
        DEFAULT_LUNA_LOW_DATASET_DIR / "validation_model_inputs.jsonl",
    ]


def _verify_isolation(input_rows: Sequence[Mapping[str, object]]) -> dict[str, int]:
    current = {_signature(row) for row in input_rows}
    overlaps = {
        path.parent.name + "_" + path.stem: len(
            current & {_signature(row) for row in _read_jsonl(path)}
        )
        for path in _prior_paths()
    }
    if any(overlaps.values()):
        raise ValueError(f"Terra screen overlaps prior data: {overlaps}")
    return overlaps


def write_terra_effort_screen(
    output_dir: Path = DEFAULT_TERRA_EFFORT_SCREEN_DIR,
) -> dict[str, object]:
    input_rows, truth_rows = build_terra_effort_screen_rows()
    overlaps = _verify_isolation(input_rows)
    output_dir.mkdir(parents=True, exist_ok=True)
    input_path = output_dir / SCREEN_MODEL_INPUTS
    truth_path = output_dir / SCREEN_TRUTH
    _write_jsonl(input_path, input_rows)
    _write_jsonl(truth_path, truth_rows)
    manifest = {
        "schema_version": SCREEN_SCHEMA_VERSION,
        "experiment": "synthetic offline Terra reasoning-effort screen",
        "seed": SCREEN_SEED,
        "split": SCREEN_SPLIT,
        "counts": {**SCREEN_COUNTS, "total": sum(SCREEN_COUNTS.values())},
        "error_distribution": SCREEN_ERROR_DISTRIBUTION,
        "composition": _verify_composition(input_rows, truth_rows),
        "model_inputs": {
            "file": input_path.name,
            "lines": len(input_rows),
            "sha256": _sha256_file(input_path),
        },
        "truth": {
            "file": truth_path.name,
            "lines": len(truth_rows),
            "sha256": _sha256_file(truth_path),
        },
        "isolation": {"overlaps": overlaps},
        "selection_rule": {
            "coverage": 1.0,
            "technical_failures": 0,
            "minimum_correct_wbs": 18,
            "maximum_clean_false_alerts": 1,
            "minimum_correct_non_wbs": 11,
            "minimum_total_correct": 44,
            "minimum_total_delta_low_minus_none": 0,
        },
        "boundaries": {
            "development_only": True,
            "calibration_or_validation_evidence": False,
            "locked_holdout_used": False,
            "luna_low_validation_used": False,
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
    verify_terra_effort_screen(output_dir)
    return manifest


def verify_terra_effort_screen(
    output_dir: Path = DEFAULT_TERRA_EFFORT_SCREEN_DIR,
) -> dict[str, object]:
    manifest = json.loads(
        (output_dir / "dataset_manifest.json").read_text(encoding="utf-8")
    )
    input_path = output_dir / manifest["model_inputs"]["file"]
    truth_path = output_dir / manifest["truth"]["file"]
    if _sha256_file(input_path) != manifest["model_inputs"]["sha256"]:
        raise ValueError("Terra screen input hash mismatch")
    if _sha256_file(truth_path) != manifest["truth"]["sha256"]:
        raise ValueError("Terra screen truth hash mismatch")
    input_rows = _read_jsonl(input_path)
    truth_rows = _read_jsonl(truth_path)
    verify_ai_qa_split_rows(
        split_name=SCREEN_SPLIT,
        input_rows=input_rows,
        truth_rows=truth_rows,
        expected_counts=SCREEN_COUNTS,
        expected_distribution=SCREEN_ERROR_DISTRIBUTION,
    )
    if _verify_composition(input_rows, truth_rows) != manifest["composition"]:
        raise ValueError("Terra screen composition metadata mismatch")
    if _verify_isolation(input_rows) != manifest["isolation"]["overlaps"]:
        raise ValueError("Terra screen isolation metadata mismatch")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Terra effort-screen data.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_TERRA_EFFORT_SCREEN_DIR,
    )
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    manifest = (
        verify_terra_effort_screen(args.output_dir)
        if args.verify_only
        else write_terra_effort_screen(args.output_dir)
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
                "boundaries": manifest["boundaries"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
