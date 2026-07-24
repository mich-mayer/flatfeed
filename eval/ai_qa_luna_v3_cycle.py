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
    build_ai_qa_custom_split,
    verify_ai_qa_split_rows,
)
from eval.ai_qa_luna_calibration import DEFAULT_LUNA_DATASET_DIR


LUNA_V3_DATASET_SCHEMA_VERSION = "1.0"
LUNA_V3_CALIBRATION_SEED = 20260725
LUNA_V3_VALIDATION_SEED = 20260726
DEFAULT_LUNA_V3_DATASET_DIR = (
    Path(__file__).with_name("datasets") / "luna_v3_cycle"
)

LUNA_V3_COUNTS = {"clean": 100, "corrupted": 100}
LUNA_V3_ERROR_DISTRIBUTION = {
    "rent_kalt": 25,
    "wbs": 20,
    "rooms": 15,
    "floor": 15,
    "address_postal_code": 10,
    "district": 8,
    "rent_warm": 7,
}
LUNA_V3_SPLITS: dict[str, dict[str, object]] = {
    "luna_v3_calibration": {
        "seed": LUNA_V3_CALIBRATION_SEED,
        "model_inputs": "calibration_model_inputs.jsonl",
        "truth": "calibration_truth.jsonl",
        "permitted_use": "one luna-v3 calibration run",
    },
    "luna_v3_validation": {
        "seed": LUNA_V3_VALIDATION_SEED,
        "model_inputs": "validation_model_inputs.jsonl",
        "truth": "validation_truth.jsonl",
        "permitted_use": "one frozen luna-v3 validation run",
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
        {
            "raw_text": row["raw_text"],
            "parser_snapshot": row["parser_snapshot"],
        }
    )


def build_luna_v3_cycle_rows() -> dict[
    str,
    tuple[list[dict[str, object]], list[dict[str, object]]],
]:
    """Build the predeclared 200+200 final Luna prompt cycle."""

    datasets = {
        split_name: build_ai_qa_custom_split(
            seed=int(config["seed"]),
            counts=LUNA_V3_COUNTS,
            error_distribution=LUNA_V3_ERROR_DISTRIBUTION,
        )
        for split_name, config in LUNA_V3_SPLITS.items()
    }
    for split_name, (input_rows, truth_rows) in datasets.items():
        verify_ai_qa_split_rows(
            split_name=split_name,
            input_rows=input_rows,
            truth_rows=truth_rows,
            expected_counts=LUNA_V3_COUNTS,
            expected_distribution=LUNA_V3_ERROR_DISTRIBUTION,
        )
    return datasets


def _prior_model_input_paths() -> dict[str, Path]:
    return {
        "original_development": (
            DEFAULT_DATASET_DIR
            / ARTIFACT_FILENAMES["development_model_inputs"]
        ),
        "locked_holdout": (
            DEFAULT_DATASET_DIR
            / ARTIFACT_FILENAMES["locked_holdout_model_inputs"]
        ),
        "luna_v1_calibration": (
            DEFAULT_LUNA_DATASET_DIR / "calibration_model_inputs.jsonl"
        ),
        "luna_v2_validation": (
            DEFAULT_LUNA_DATASET_DIR / "validation_model_inputs.jsonl"
        ),
    }


def _verify_isolation(
    datasets: Mapping[
        str,
        tuple[Sequence[Mapping[str, object]], Sequence[Mapping[str, object]]],
    ],
) -> dict[str, int]:
    generated = {
        split_name: {_signature(row) for row in input_rows}
        for split_name, (input_rows, _truth_rows) in datasets.items()
    }
    calibration = generated["luna_v3_calibration"]
    validation = generated["luna_v3_validation"]
    overlaps = {
        "calibration_validation": len(calibration & validation),
    }
    for prior_name, path in _prior_model_input_paths().items():
        prior = {_signature(row) for row in _read_jsonl(path)}
        overlaps[f"calibration_{prior_name}"] = len(calibration & prior)
        overlaps[f"validation_{prior_name}"] = len(validation & prior)
    if any(overlaps.values()):
        raise ValueError(f"Luna-v3 dataset overlap: {overlaps}")
    return overlaps


def write_luna_v3_cycle_datasets(
    output_dir: Path = DEFAULT_LUNA_V3_DATASET_DIR,
) -> dict[str, object]:
    """Write the final Luna calibration and validation cycle."""

    datasets = build_luna_v3_cycle_rows()
    overlaps = _verify_isolation(datasets)
    output_dir.mkdir(parents=True, exist_ok=True)

    split_manifest: dict[str, object] = {}
    for split_name, (input_rows, truth_rows) in datasets.items():
        config = LUNA_V3_SPLITS[split_name]
        input_path = output_dir / str(config["model_inputs"])
        truth_path = output_dir / str(config["truth"])
        _write_jsonl(input_path, input_rows)
        _write_jsonl(truth_path, truth_rows)
        split_manifest[split_name] = {
            "seed": config["seed"],
            "counts": {
                **LUNA_V3_COUNTS,
                "total": sum(LUNA_V3_COUNTS.values()),
            },
            "error_distribution": LUNA_V3_ERROR_DISTRIBUTION,
            "permitted_use": config["permitted_use"],
            "artifacts": {
                "model_inputs": _artifact_entry(
                    input_path,
                    lines=len(input_rows),
                ),
                "truth": _artifact_entry(
                    truth_path,
                    lines=len(truth_rows),
                ),
            },
        }

    manifest: dict[str, object] = {
        "schema_version": LUNA_V3_DATASET_SCHEMA_VERSION,
        "experiment": "synthetic offline AI QA Luna-v3 final cycle",
        "hash_algorithm": "SHA-256",
        "serialization": {
            "encoding": "UTF-8",
            "format": "JSON Lines",
            "json_keys": "sorted",
            "line_ending": "LF",
        },
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
            "prompt_changes_after_validation": False,
        },
    }
    manifest_path = output_dir / "dataset_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    verify_luna_v3_cycle_datasets(output_dir)
    return manifest


def verify_luna_v3_cycle_datasets(
    output_dir: Path = DEFAULT_LUNA_V3_DATASET_DIR,
) -> dict[str, object]:
    """Verify schemas, hashes, exact distribution, and split isolation."""

    manifest_path = output_dir / "dataset_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != LUNA_V3_DATASET_SCHEMA_VERSION:
        raise ValueError("Luna-v3 manifest schema is incorrect")

    datasets: dict[
        str,
        tuple[list[dict[str, object]], list[dict[str, object]]],
    ] = {}
    for split_name, config in LUNA_V3_SPLITS.items():
        split = manifest["splits"][split_name]
        if split.get("seed") != config["seed"]:
            raise ValueError(f"{split_name} seed is incorrect")
        if split.get("counts") != {
            **LUNA_V3_COUNTS,
            "total": sum(LUNA_V3_COUNTS.values()),
        }:
            raise ValueError(f"{split_name} counts are incorrect")
        if split.get("error_distribution") != LUNA_V3_ERROR_DISTRIBUTION:
            raise ValueError(f"{split_name} distribution is incorrect")

        input_artifact = split["artifacts"]["model_inputs"]
        truth_artifact = split["artifacts"]["truth"]
        input_path = output_dir / input_artifact["file"]
        truth_path = output_dir / truth_artifact["file"]
        if _sha256_file(input_path) != input_artifact["sha256"]:
            raise ValueError(f"{split_name} model-input hash mismatch")
        if _sha256_file(truth_path) != truth_artifact["sha256"]:
            raise ValueError(f"{split_name} truth hash mismatch")
        input_rows = _read_jsonl(input_path)
        truth_rows = _read_jsonl(truth_path)
        verify_ai_qa_split_rows(
            split_name=split_name,
            input_rows=input_rows,
            truth_rows=truth_rows,
            expected_counts=LUNA_V3_COUNTS,
            expected_distribution=LUNA_V3_ERROR_DISTRIBUTION,
        )
        datasets[split_name] = (input_rows, truth_rows)

    overlaps = _verify_isolation(datasets)
    if manifest.get("isolation", {}).get("overlaps") != overlaps:
        raise ValueError("Luna-v3 isolation metadata is incorrect")
    return manifest


def public_summary(manifest: Mapping[str, object]) -> dict[str, object]:
    """Expose reproducibility metadata without revealing any answer row."""

    return {
        "splits": {
            split_name: {
                "seed": split["seed"],
                "counts": split["counts"],
                "error_distribution": split["error_distribution"],
                "model_inputs_sha256": split["artifacts"]["model_inputs"][
                    "sha256"
                ],
                "truth_sha256": split["artifacts"]["truth"]["sha256"],
            }
            for split_name, split in manifest["splits"].items()
        },
        "overlaps": manifest["isolation"]["overlaps"],
        "boundaries": manifest["boundaries"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate the final 200+200 Luna-v3 offline eval cycle.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_LUNA_V3_DATASET_DIR,
    )
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    manifest = (
        verify_luna_v3_cycle_datasets(args.output_dir)
        if args.verify_only
        else write_luna_v3_cycle_datasets(args.output_dir)
    )
    print(json.dumps(public_summary(manifest), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
