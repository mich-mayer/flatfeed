from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from eval.ai_qa_datasets import (
    ARTIFACT_FILENAMES,
    DEFAULT_DATASET_DIR,
    build_ai_qa_split_from_clean_cases,
    verify_ai_qa_split_rows,
)
from eval.ai_qa_luna_calibration import DEFAULT_LUNA_DATASET_DIR
from eval.ai_qa_luna_effort_screen import DEFAULT_LUNA_EFFORT_SCREEN_DIR
from eval.ai_qa_luna_v3_cycle import DEFAULT_LUNA_V3_DATASET_DIR
from eval.ai_qa_luna_v4_cycle import DEFAULT_LUNA_V4_DATASET_DIR
from eval.ai_qa_luna_v5_cycle import (
    DEFAULT_LUNA_V5_DATASET_DIR,
    LUNA_V5_COUNTS,
    LUNA_V5_ERROR_DISTRIBUTION,
    _verify_semantic_balance,
    generate_balanced_wbs_cases,
)


LUNA_LOW_DATASET_SCHEMA_VERSION = "1.0"
LUNA_LOW_CALIBRATION_SEED = 20260801
LUNA_LOW_VALIDATION_SEED = 20260802
DEFAULT_LUNA_LOW_DATASET_DIR = (
    Path(__file__).with_name("datasets") / "luna_low_cycle"
)

LUNA_LOW_COUNTS = dict(LUNA_V5_COUNTS)
LUNA_LOW_ERROR_DISTRIBUTION = dict(LUNA_V5_ERROR_DISTRIBUTION)
LUNA_LOW_SPLITS: dict[str, dict[str, object]] = {
    "luna_low_calibration": {
        "seed": LUNA_LOW_CALIBRATION_SEED,
        "model_inputs": "calibration_model_inputs.jsonl",
        "truth": "calibration_truth.jsonl",
        "permitted_use": "one Luna low-effort calibration run",
    },
    "luna_low_validation": {
        "seed": LUNA_LOW_VALIDATION_SEED,
        "model_inputs": "validation_model_inputs.jsonl",
        "truth": "validation_truth.jsonl",
        "permitted_use": "one frozen Luna low-effort validation run",
    },
}


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


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


def build_luna_low_cycle_rows() -> dict[
    str, tuple[list[dict[str, object]], list[dict[str, object]]]
]:
    datasets = {}
    for split_name, config in LUNA_LOW_SPLITS.items():
        seed = int(config["seed"])
        source_cases = generate_balanced_wbs_cases(seed=seed)
        rows = build_ai_qa_split_from_clean_cases(
            source_cases=source_cases,
            seed=seed,
            counts=LUNA_LOW_COUNTS,
            error_distribution=LUNA_LOW_ERROR_DISTRIBUTION,
        )
        verify_ai_qa_split_rows(
            split_name=split_name,
            input_rows=rows[0],
            truth_rows=rows[1],
            expected_counts=LUNA_LOW_COUNTS,
            expected_distribution=LUNA_LOW_ERROR_DISTRIBUTION,
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
        "luna_v5_calibration": DEFAULT_LUNA_V5_DATASET_DIR
        / "calibration_model_inputs.jsonl",
        "luna_v5_validation": DEFAULT_LUNA_V5_DATASET_DIR
        / "validation_model_inputs.jsonl",
        "luna_effort_screen": DEFAULT_LUNA_EFFORT_SCREEN_DIR
        / "model_inputs.jsonl",
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
    calibration = generated["luna_low_calibration"]
    validation = generated["luna_low_validation"]
    overlaps = {"calibration_validation": len(calibration & validation)}
    for name, path in _prior_model_input_paths().items():
        prior = {_signature(row) for row in _read_jsonl(path)}
        overlaps[f"calibration_{name}"] = len(calibration & prior)
        overlaps[f"validation_{name}"] = len(validation & prior)
    if any(overlaps.values()):
        raise ValueError(f"Luna-low dataset overlap: {overlaps}")
    return overlaps


def write_luna_low_cycle_datasets(
    output_dir: Path = DEFAULT_LUNA_LOW_DATASET_DIR,
) -> dict[str, object]:
    datasets = build_luna_low_cycle_rows()
    overlaps = _verify_isolation(datasets)
    output_dir.mkdir(parents=True, exist_ok=True)
    split_manifest: dict[str, object] = {}
    for split_name, (input_rows, truth_rows) in datasets.items():
        config = LUNA_LOW_SPLITS[split_name]
        input_path = output_dir / str(config["model_inputs"])
        truth_path = output_dir / str(config["truth"])
        _write_jsonl(input_path, input_rows)
        _write_jsonl(truth_path, truth_rows)
        split_manifest[split_name] = {
            "seed": config["seed"],
            "counts": {
                **LUNA_LOW_COUNTS,
                "total": sum(LUNA_LOW_COUNTS.values()),
            },
            "error_distribution": LUNA_LOW_ERROR_DISTRIBUTION,
            "wbs_semantic_balance": _verify_semantic_balance(
                input_rows,
                truth_rows,
            ),
            "permitted_use": config["permitted_use"],
            "artifacts": {
                "model_inputs": _artifact_entry(
                    input_path,
                    lines=len(input_rows),
                ),
                "truth": _artifact_entry(truth_path, lines=len(truth_rows)),
            },
        }
    manifest: dict[str, object] = {
        "schema_version": LUNA_LOW_DATASET_SCHEMA_VERSION,
        "experiment": "synthetic offline AI QA Luna low-effort cycle",
        "hypothesis": (
            "Luna-v5 with low reasoning can preserve specificity while "
            "improving close normalized WBS-set error detection."
        ),
        "hash_algorithm": "SHA-256",
        "configuration": {
            "model": "gpt-5.6-luna",
            "reasoning_effort": "low",
            "prompt_version": "luna-v5",
            "max_output_tokens": 256,
            "retries": 0,
            "strict_structured_outputs": True,
        },
        "splits": split_manifest,
        "isolation": {
            "comparison_basis": "raw_text plus parser_snapshot",
            "overlaps": overlaps,
        },
        "boundaries": {
            "reasoning_screen_reused": False,
            "validation_requires_passing_calibration_freeze": True,
            "validation_authorized_now": False,
            "locked_holdout_used_for_inference": False,
            "locked_holdout_truth_read": False,
            "locked_holdout_modified": False,
            "openai_called_during_generation": False,
            "product_runtime_modified": False,
            "sol_or_terra_authorized": False,
        },
    }
    manifest_path = output_dir / "dataset_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    verify_luna_low_cycle_datasets(output_dir)
    return manifest


def verify_luna_low_cycle_datasets(
    output_dir: Path = DEFAULT_LUNA_LOW_DATASET_DIR,
) -> dict[str, object]:
    manifest_path = output_dir / "dataset_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != LUNA_LOW_DATASET_SCHEMA_VERSION:
        raise ValueError("Luna-low manifest schema is incorrect")
    datasets = {}
    for split_name in LUNA_LOW_SPLITS:
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
            expected_counts=LUNA_LOW_COUNTS,
            expected_distribution=LUNA_LOW_ERROR_DISTRIBUTION,
        )
        balance = _verify_semantic_balance(*rows)
        if balance != split["wbs_semantic_balance"]:
            raise ValueError(f"{split_name} WBS balance metadata mismatch")
        datasets[split_name] = rows
    overlaps = _verify_isolation(datasets)
    if overlaps != manifest["isolation"]["overlaps"]:
        raise ValueError("Luna-low isolation metadata mismatch")
    return manifest


def public_summary(manifest: Mapping[str, object]) -> dict[str, object]:
    return {
        "hypothesis": manifest["hypothesis"],
        "configuration": manifest["configuration"],
        "splits": {
            name: {
                "seed": split["seed"],
                "counts": split["counts"],
                "error_distribution": split["error_distribution"],
                "wbs_semantic_balance": split["wbs_semantic_balance"],
                "model_inputs_sha256": split["artifacts"]["model_inputs"][
                    "sha256"
                ],
                "truth_sha256": split["artifacts"]["truth"]["sha256"],
            }
            for name, split in manifest["splits"].items()
        },
        "overlaps": manifest["isolation"]["overlaps"],
        "boundaries": manifest["boundaries"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate the independent Luna low-effort eval cycle."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_LUNA_LOW_DATASET_DIR,
    )
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    manifest = (
        verify_luna_low_cycle_datasets(args.output_dir)
        if args.verify_only
        else write_luna_low_cycle_datasets(args.output_dir)
    )
    print(json.dumps(public_summary(manifest), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
