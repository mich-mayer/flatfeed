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
    DEVELOPMENT_COUNTS,
    DEVELOPMENT_ERROR_DISTRIBUTION,
    build_ai_qa_dataset_rows,
    verify_ai_qa_split_rows,
)


CALIBRATION_DATASET_SCHEMA_VERSION = "1.0"
CALIBRATION_SEED = 20260723
VALIDATION_SEED = 20260724
DEFAULT_LUNA_DATASET_DIR = Path(__file__).with_name("datasets") / "luna_calibration"

LUNA_SPLITS: dict[str, dict[str, object]] = {
    "luna_calibration": {
        "seed": CALIBRATION_SEED,
        "model_inputs": "calibration_model_inputs.jsonl",
        "truth": "calibration_truth.jsonl",
        "permitted_use": "one luna-v1 calibration run",
    },
    "luna_validation": {
        "seed": VALIDATION_SEED,
        "model_inputs": "validation_model_inputs.jsonl",
        "truth": "validation_truth.jsonl",
        "permitted_use": "one frozen luna-v1 validation run",
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
    serialized = "".join(f"{_canonical_json(row)}\n" for row in rows)
    path.write_text(serialized, encoding="utf-8")


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


def build_luna_calibration_rows() -> dict[
    str,
    tuple[list[dict[str, object]], list[dict[str, object]]],
]:
    """Build two fresh development-sized splits without calling OpenAI."""

    datasets = {
        split_name: build_ai_qa_dataset_rows(seed=int(config["seed"]))[
            "development"
        ]
        for split_name, config in LUNA_SPLITS.items()
    }
    for split_name, (input_rows, truth_rows) in datasets.items():
        verify_ai_qa_split_rows(
            split_name=split_name,
            input_rows=input_rows,
            truth_rows=truth_rows,
        )
    return datasets


def _existing_case_signatures() -> dict[str, set[str]]:
    paths = {
        "original_development": (
            DEFAULT_DATASET_DIR
            / ARTIFACT_FILENAMES["development_model_inputs"]
        ),
        "locked_holdout": (
            DEFAULT_DATASET_DIR
            / ARTIFACT_FILENAMES["locked_holdout_model_inputs"]
        ),
    }
    return {
        name: {_signature(row) for row in _read_jsonl(path)}
        for name, path in paths.items()
    }


def _verify_isolation(
    datasets: Mapping[
        str,
        tuple[Sequence[Mapping[str, object]], Sequence[Mapping[str, object]]],
    ],
) -> dict[str, int]:
    existing = _existing_case_signatures()
    generated = {
        split_name: {_signature(row) for row in input_rows}
        for split_name, (input_rows, _truth_rows) in datasets.items()
    }
    overlaps = {
        "calibration_validation": len(
            generated["luna_calibration"]
            & generated["luna_validation"]
        ),
        "calibration_original_development": len(
            generated["luna_calibration"]
            & existing["original_development"]
        ),
        "calibration_locked_holdout": len(
            generated["luna_calibration"]
            & existing["locked_holdout"]
        ),
        "validation_original_development": len(
            generated["luna_validation"]
            & existing["original_development"]
        ),
        "validation_locked_holdout": len(
            generated["luna_validation"]
            & existing["locked_holdout"]
        ),
    }
    if any(overlaps.values()):
        raise ValueError(f"Luna calibration dataset overlap: {overlaps}")
    return overlaps


def write_luna_calibration_datasets(
    output_dir: Path = DEFAULT_LUNA_DATASET_DIR,
) -> dict[str, object]:
    """Write fresh Luna calibration and frozen validation artifacts."""

    datasets = build_luna_calibration_rows()
    overlaps = _verify_isolation(datasets)
    output_dir.mkdir(parents=True, exist_ok=True)

    split_manifest: dict[str, object] = {}
    for split_name, (input_rows, truth_rows) in datasets.items():
        config = LUNA_SPLITS[split_name]
        input_path = output_dir / str(config["model_inputs"])
        truth_path = output_dir / str(config["truth"])
        _write_jsonl(input_path, input_rows)
        _write_jsonl(truth_path, truth_rows)
        split_manifest[split_name] = {
            "seed": config["seed"],
            "counts": {
                **DEVELOPMENT_COUNTS,
                "total": sum(DEVELOPMENT_COUNTS.values()),
            },
            "error_distribution": DEVELOPMENT_ERROR_DISTRIBUTION,
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
        "schema_version": CALIBRATION_DATASET_SCHEMA_VERSION,
        "experiment": "synthetic offline AI QA Luna calibration",
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
            "locked_holdout_read_for_generation": False,
            "locked_holdout_modified": False,
            "openai_called": False,
            "product_runtime_modified": False,
        },
    }
    manifest_path = output_dir / "dataset_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    verify_luna_calibration_datasets(output_dir)
    return manifest


def verify_luna_calibration_datasets(
    output_dir: Path = DEFAULT_LUNA_DATASET_DIR,
) -> dict[str, object]:
    """Verify hashes, schemas, reproducibility metadata, and isolation."""

    manifest_path = output_dir / "dataset_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != CALIBRATION_DATASET_SCHEMA_VERSION:
        raise ValueError("Luna calibration manifest schema is incorrect")

    datasets: dict[
        str,
        tuple[list[dict[str, object]], list[dict[str, object]]],
    ] = {}
    for split_name, config in LUNA_SPLITS.items():
        split = manifest["splits"][split_name]
        if split.get("seed") != config["seed"]:
            raise ValueError(f"{split_name} seed is incorrect")
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
        )
        datasets[split_name] = (input_rows, truth_rows)

    actual_overlaps = _verify_isolation(datasets)
    if manifest.get("isolation", {}).get("overlaps") != actual_overlaps:
        raise ValueError("Luna calibration isolation metadata is incorrect")
    return manifest


def public_summary(manifest: Mapping[str, object]) -> dict[str, object]:
    """Return statistics and hashes without exposing truth rows."""

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
        description="Generate fresh Luna calibration datasets without OpenAI.",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_LUNA_DATASET_DIR)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    manifest = (
        verify_luna_calibration_datasets(args.output_dir)
        if args.verify_only
        else write_luna_calibration_datasets(args.output_dir)
    )
    print(json.dumps(public_summary(manifest), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
