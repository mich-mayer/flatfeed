from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

from eval.ai_qa_clean_generator import CleanAIQACase, WBS_TEXTS, generate_clean_ai_qa_cases
from eval.ai_qa_datasets import (
    ARTIFACT_FILENAMES,
    DEFAULT_DATASET_DIR,
    build_ai_qa_split_from_clean_cases,
    verify_ai_qa_split_rows,
)
from eval.ai_qa_luna_calibration import DEFAULT_LUNA_DATASET_DIR
from eval.ai_qa_luna_v3_cycle import DEFAULT_LUNA_V3_DATASET_DIR
from eval.ai_qa_luna_v4_cycle import DEFAULT_LUNA_V4_DATASET_DIR
from eval.ai_qa_scorer import TRUTH_FIELD_TO_ERROR_FIELD


LUNA_V5_DATASET_SCHEMA_VERSION = "1.0"
LUNA_V5_CALIBRATION_SEED = 20260729
LUNA_V5_VALIDATION_SEED = 20260730
DEFAULT_LUNA_V5_DATASET_DIR = Path(__file__).with_name("datasets") / "luna_v5_cycle"

LUNA_V5_COUNTS = {"clean": 140, "corrupted": 140}
LUNA_V5_ERROR_DISTRIBUTION = {
    "wbs": 56,
    "rent_kalt": 21,
    "rooms": 21,
    "address_postal_code": 14,
    "district": 10,
    "floor": 10,
    "rent_warm": 8,
}
LUNA_V5_SPLITS: dict[str, dict[str, object]] = {
    "luna_v5_calibration": {
        "seed": LUNA_V5_CALIBRATION_SEED,
        "model_inputs": "calibration_model_inputs.jsonl",
        "truth": "calibration_truth.jsonl",
        "permitted_use": "one luna-v5 calibration run",
    },
    "luna_v5_validation": {
        "seed": LUNA_V5_VALIDATION_SEED,
        "model_inputs": "validation_model_inputs.jsonl",
        "truth": "validation_truth.jsonl",
        "permitted_use": "one frozen luna-v5 validation run",
    },
}

LUNA_V5_WBS_PHRASES: dict[str, tuple[str, ...]] = {
    "No WBS required": (
        "Die Wohnung ist freifinanziert; ein WBS ist nicht erforderlich.",
        "Eine Bewerbung ist ohne Wohnberechtigungsschein möglich.",
        "Für dieses Angebot wird kein WBS verlangt.",
        "WBS: nicht erforderlich.",
    ),
    "WBS required, type unknown": (
        "Ein gültiger WBS ist erforderlich; eine Stufe wird nicht genannt.",
        "Nur mit Wohnberechtigungsschein, Förderstufe nicht angegeben.",
        "Die Wohnung ist WBS-gebunden, ohne Angabe eines Prozentsatzes.",
        "WBS erforderlich; zulässige Einkommensstufe offen.",
    ),
    "100": (
        "Voraussetzung ist ausschließlich ein WBS 100.",
        "Zugelassen ist genau die WBS-Stufe 100 %.",
        "Bewerbung nur mit Wohnberechtigungsschein 100.",
        "WBS-Bindung: 100 %, keine weitere Stufe.",
    ),
    "100, 140": (
        "Bewerbung mit WBS 100-140 % möglich.",
        "Zugelassen sind ausschließlich WBS 100 oder WBS 140.",
        "Akzeptiert wird ein WBS bis einschließlich 140 %.",
        "WBS-Obergrenze 140 %; zulässige Stufen sind 100 % und 140 %.",
    ),
    "160, 180, 220": (
        "Benötigt wird ein Wohnberechtigungsschein 141-220 %.",
        "WBS 141-220 %.",
        "Zulässig ist ein WBS größer als 140 % und höchstens 220 %.",
        "Akzeptierte WBS-Stufen: 160 %, 180 % oder 220 %.",
    ),
    "140, 160, 180, 220": (
        "Zulässig ist ein WBS 140-220 %.",
        "Akzeptiert wird ein WBS von 140 % bis einschließlich 220 %.",
        "Akzeptierte WBS-Stufen: 140 %, 160 %, 180 % oder 220 %.",
        "Ab WBS 140 bis WBS 220 sind alle unterstützten Stufen zulässig.",
    ),
    "100, 140, 160, 180": (
        "Eine Bewerbung ist bis WBS 180 möglich.",
        "Zulässig ist ein WBS 100-180 %.",
        "Akzeptierte WBS-Stufen: 100 %, 140 %, 160 % oder 180 %.",
        "Höchstens WBS 180; zulässig sind 100 %, 140 %, 160 % und 180 %.",
    ),
}


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _derived_seed(seed: int, namespace: str) -> int:
    payload = f"{seed}:{namespace}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, object]]) -> None:
    path.write_text(
        "".join(f"{_canonical_json(row)}\n" for row in rows),
        encoding="utf-8",
    )


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as artifact:
        for line_number, line in enumerate(artifact, start=1):
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path.name}:{line_number} must be an object")
            rows.append(value)
    return rows


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as artifact:
        for chunk in iter(lambda: artifact.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact_entry(path: Path, *, lines: int) -> dict[str, object]:
    return {
        "bytes": path.stat().st_size,
        "file": path.name,
        "lines": lines,
        "sha256": _sha256_file(path),
    }


def _signature(row: Mapping[str, object]) -> str:
    return _canonical_json(
        {"raw_text": row["raw_text"], "parser_snapshot": row["parser_snapshot"]}
    )


def _expanded_corruption_fields(seed: int) -> list[str]:
    fields = [
        field
        for field, count in LUNA_V5_ERROR_DISTRIBUTION.items()
        for _ in range(count)
    ]
    random.Random(_derived_seed(seed, "custom-field-order")).shuffle(fields)
    return fields


def _balanced_values(values: Sequence[str], each: int, *, seed: int) -> list[str]:
    result = [value for value in values for _ in range(each)]
    random.Random(seed).shuffle(result)
    return result


def _replace_wbs_semantics(
    case: CleanAIQACase,
    *,
    expected_wbs: str,
    phrase: str,
) -> CleanAIQACase:
    matches = [base for base in WBS_TEXTS if case.raw_text.endswith(base)]
    if len(matches) != 1:
        raise ValueError("source case lacks exactly one canonical WBS suffix")
    raw_text = case.raw_text[: -len(matches[0])] + phrase
    snapshot = replace(case.parser_snapshot, display_wbs=expected_wbs)
    digest = hashlib.sha256(
        f"{raw_text}\n{_canonical_json(snapshot.as_dict())}".encode("utf-8")
    ).hexdigest()[:12]
    return replace(
        case,
        case_id=f"clean-v5-{digest}",
        raw_text=raw_text,
        parser_snapshot=snapshot,
        format_variant=f"{case.format_variant}+balanced_wbs_semantics",
    )


def generate_balanced_wbs_cases(*, seed: int) -> list[CleanAIQACase]:
    families = tuple(LUNA_V5_WBS_PHRASES)
    clean_families = _balanced_values(
        families,
        20,
        seed=_derived_seed(seed, "v5-clean-wbs-families"),
    )
    wbs_corrupted_families = _balanced_values(
        families,
        8,
        seed=_derived_seed(seed, "v5-wbs-corrupted-families"),
    )
    non_wbs_corrupted_families = _balanced_values(
        families,
        12,
        seed=_derived_seed(seed, "v5-non-wbs-corrupted-families"),
    )
    corruption_fields = _expanded_corruption_fields(seed)
    corrupted_families: list[str] = []
    wbs_index = 0
    non_wbs_index = 0
    for field in corruption_fields:
        if field == "wbs":
            corrupted_families.append(wbs_corrupted_families[wbs_index])
            wbs_index += 1
        else:
            corrupted_families.append(
                non_wbs_corrupted_families[non_wbs_index]
            )
            non_wbs_index += 1
    family_order = [*clean_families, *corrupted_families]
    source_cases = generate_clean_ai_qa_cases(
        count=sum(LUNA_V5_COUNTS.values()),
        seed=_derived_seed(seed, "v5-clean-source-cases"),
    )
    offsets = {
        family: random.Random(_derived_seed(seed, f"phrase:{family}")).randrange(
            len(phrases)
        )
        for family, phrases in LUNA_V5_WBS_PHRASES.items()
    }
    occurrences: Counter[str] = Counter()
    result: list[CleanAIQACase] = []
    if len(source_cases) != len(family_order):
        raise ValueError("source case and WBS family counts differ")
    for case, family in zip(source_cases, family_order):
        phrases = LUNA_V5_WBS_PHRASES[family]
        phrase = phrases[(offsets[family] + occurrences[family]) % len(phrases)]
        occurrences[family] += 1
        result.append(
            _replace_wbs_semantics(
                case,
                expected_wbs=family,
                phrase=phrase,
            )
        )
    return result


def _find_expected_wbs(raw_text: str) -> str:
    matches = [
        expected
        for expected, phrases in LUNA_V5_WBS_PHRASES.items()
        for phrase in phrases
        if raw_text.endswith(phrase)
    ]
    if len(matches) != 1:
        raise ValueError("row lacks exactly one curated Luna-v5 WBS phrase")
    return matches[0]


def _verify_semantic_balance(
    input_rows: Sequence[Mapping[str, object]],
    truth_rows: Sequence[Mapping[str, object]],
) -> dict[str, dict[str, int]]:
    counters = {family: Counter() for family in LUNA_V5_WBS_PHRASES}
    if len(input_rows) != len(truth_rows):
        raise ValueError("input and truth row counts differ")
    for input_row, truth_row in zip(input_rows, truth_rows):
        if input_row["case_id"] != truth_row["case_id"]:
            raise ValueError("input and truth row order differs")
        family = _find_expected_wbs(str(input_row["raw_text"]))
        if truth_row["case_type"] == "clean":
            counters[family]["clean"] += 1
            continue
        expected_field = TRUTH_FIELD_TO_ERROR_FIELD[
            str(truth_row["corrupted_field"])
        ]
        counters[family][
            "wbs_corrupted" if expected_field == "wbs" else "non_wbs_corrupted"
        ] += 1
    expected = {"clean": 20, "wbs_corrupted": 8, "non_wbs_corrupted": 12}
    result = {family: dict(counter) for family, counter in counters.items()}
    if any(result[family] != expected for family in result):
        raise ValueError(f"Luna-v5 WBS semantic balance mismatch: {result}")
    return result


def build_luna_v5_cycle_rows() -> dict[
    str, tuple[list[dict[str, object]], list[dict[str, object]]]
]:
    datasets = {}
    for split_name, config in LUNA_V5_SPLITS.items():
        seed = int(config["seed"])
        source_cases = generate_balanced_wbs_cases(seed=seed)
        rows = build_ai_qa_split_from_clean_cases(
            source_cases=source_cases,
            seed=seed,
            counts=LUNA_V5_COUNTS,
            error_distribution=LUNA_V5_ERROR_DISTRIBUTION,
        )
        verify_ai_qa_split_rows(
            split_name=split_name,
            input_rows=rows[0],
            truth_rows=rows[1],
            expected_counts=LUNA_V5_COUNTS,
            expected_distribution=LUNA_V5_ERROR_DISTRIBUTION,
        )
        _verify_semantic_balance(*rows)
        datasets[split_name] = rows
    return datasets


def _prior_model_input_paths() -> dict[str, Path]:
    return {
        "original_development": DEFAULT_DATASET_DIR
        / ARTIFACT_FILENAMES["development_model_inputs"],
        "locked_holdout": DEFAULT_DATASET_DIR
        / ARTIFACT_FILENAMES["locked_holdout_model_inputs"],
        "luna_v1_calibration": DEFAULT_LUNA_DATASET_DIR
        / "calibration_model_inputs.jsonl",
        "luna_v2_validation": DEFAULT_LUNA_DATASET_DIR
        / "validation_model_inputs.jsonl",
        "luna_v3_calibration": DEFAULT_LUNA_V3_DATASET_DIR
        / "calibration_model_inputs.jsonl",
        "luna_v3_validation": DEFAULT_LUNA_V3_DATASET_DIR
        / "validation_model_inputs.jsonl",
        "luna_v4_calibration": DEFAULT_LUNA_V4_DATASET_DIR
        / "calibration_model_inputs.jsonl",
        "luna_v4_validation": DEFAULT_LUNA_V4_DATASET_DIR
        / "validation_model_inputs.jsonl",
    }


def _verify_isolation(
    datasets: Mapping[
        str,
        tuple[Sequence[Mapping[str, object]], Sequence[Mapping[str, object]]],
    ],
) -> dict[str, int]:
    generated = {
        split: {_signature(row) for row in rows[0]}
        for split, rows in datasets.items()
    }
    calibration = generated["luna_v5_calibration"]
    validation = generated["luna_v5_validation"]
    overlaps = {"calibration_validation": len(calibration & validation)}
    for name, path in _prior_model_input_paths().items():
        prior = {_signature(row) for row in _read_jsonl(path)}
        overlaps[f"calibration_{name}"] = len(calibration & prior)
        overlaps[f"validation_{name}"] = len(validation & prior)
    if any(overlaps.values()):
        raise ValueError(f"Luna-v5 dataset overlap: {overlaps}")
    return overlaps


def write_luna_v5_cycle_datasets(
    output_dir: Path = DEFAULT_LUNA_V5_DATASET_DIR,
) -> dict[str, object]:
    datasets = build_luna_v5_cycle_rows()
    overlaps = _verify_isolation(datasets)
    output_dir.mkdir(parents=True, exist_ok=True)
    split_manifest: dict[str, object] = {}
    for split_name, (input_rows, truth_rows) in datasets.items():
        config = LUNA_V5_SPLITS[split_name]
        input_path = output_dir / str(config["model_inputs"])
        truth_path = output_dir / str(config["truth"])
        _write_jsonl(input_path, input_rows)
        _write_jsonl(truth_path, truth_rows)
        split_manifest[split_name] = {
            "seed": config["seed"],
            "counts": {**LUNA_V5_COUNTS, "total": sum(LUNA_V5_COUNTS.values())},
            "error_distribution": LUNA_V5_ERROR_DISTRIBUTION,
            "wbs_semantic_balance": _verify_semantic_balance(input_rows, truth_rows),
            "permitted_use": config["permitted_use"],
            "artifacts": {
                "model_inputs": _artifact_entry(input_path, lines=len(input_rows)),
                "truth": _artifact_entry(truth_path, lines=len(truth_rows)),
            },
        }
    manifest: dict[str, object] = {
        "schema_version": LUNA_V5_DATASET_SCHEMA_VERSION,
        "experiment": "synthetic offline AI QA Luna-v5 balanced WBS recovery cycle",
        "hypothesis": (
            "A normalized-set prompt plus balanced WBS negative controls can "
            "preserve WBS recall without WBS-salience false alerts."
        ),
        "hash_algorithm": "SHA-256",
        "splits": split_manifest,
        "isolation": {
            "comparison_basis": "raw_text plus parser_snapshot",
            "overlaps": overlaps,
        },
        "boundaries": {
            "locked_holdout_used_for_inference": False,
            "locked_holdout_truth_read": False,
            "locked_holdout_modified": False,
            "openai_called_during_generation": False,
            "product_runtime_modified": False,
            "maximum_new_prompt_versions": 1,
            "luna_v6_permitted_by_default": False,
        },
    }
    manifest_path = output_dir / "dataset_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    verify_luna_v5_cycle_datasets(output_dir)
    return manifest


def verify_luna_v5_cycle_datasets(
    output_dir: Path = DEFAULT_LUNA_V5_DATASET_DIR,
) -> dict[str, object]:
    manifest_path = output_dir / "dataset_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != LUNA_V5_DATASET_SCHEMA_VERSION:
        raise ValueError("Luna-v5 manifest schema is incorrect")
    datasets = {}
    for split_name, config in LUNA_V5_SPLITS.items():
        split = manifest["splits"][split_name]
        input_entry = split["artifacts"]["model_inputs"]
        truth_entry = split["artifacts"]["truth"]
        input_path = output_dir / input_entry["file"]
        truth_path = output_dir / truth_entry["file"]
        if _sha256_file(input_path) != input_entry["sha256"]:
            raise ValueError(f"{split_name} input hash mismatch")
        if _sha256_file(truth_path) != truth_entry["sha256"]:
            raise ValueError(f"{split_name} truth hash mismatch")
        rows = (_read_jsonl(input_path), _read_jsonl(truth_path))
        verify_ai_qa_split_rows(
            split_name=split_name,
            input_rows=rows[0],
            truth_rows=rows[1],
            expected_counts=LUNA_V5_COUNTS,
            expected_distribution=LUNA_V5_ERROR_DISTRIBUTION,
        )
        balance = _verify_semantic_balance(*rows)
        if balance != split["wbs_semantic_balance"]:
            raise ValueError(f"{split_name} WBS balance metadata mismatch")
        datasets[split_name] = rows
    overlaps = _verify_isolation(datasets)
    if overlaps != manifest["isolation"]["overlaps"]:
        raise ValueError("Luna-v5 isolation metadata mismatch")
    return manifest


def public_summary(manifest: Mapping[str, object]) -> dict[str, object]:
    return {
        "hypothesis": manifest["hypothesis"],
        "splits": {
            name: {
                "seed": split["seed"],
                "counts": split["counts"],
                "error_distribution": split["error_distribution"],
                "wbs_semantic_balance": split["wbs_semantic_balance"],
                "model_inputs_sha256": split["artifacts"]["model_inputs"]["sha256"],
                "truth_sha256": split["artifacts"]["truth"]["sha256"],
            }
            for name, split in manifest["splits"].items()
        },
        "overlaps": manifest["isolation"]["overlaps"],
        "boundaries": manifest["boundaries"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the final Luna-v5 eval cycle.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_LUNA_V5_DATASET_DIR)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    manifest = (
        verify_luna_v5_cycle_datasets(args.output_dir)
        if args.verify_only
        else write_luna_v5_cycle_datasets(args.output_dir)
    )
    print(json.dumps(public_summary(manifest), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
