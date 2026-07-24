from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path

from eval.ai_qa_datasets import (
    build_ai_qa_split_from_clean_cases,
    verify_ai_qa_split_rows,
)
from eval.ai_qa_luna_low_cycle import (
    LUNA_LOW_COUNTS,
    LUNA_LOW_ERROR_DISTRIBUTION,
    _artifact_entry,
    _canonical_json,
    _read_jsonl,
    _sha256_file,
    _signature,
)
from eval.ai_qa_luna_v5_cycle import (
    _verify_semantic_balance,
    generate_balanced_wbs_cases,
)
from eval.ai_qa_terra_high_screen import (
    DEFAULT_TERRA_HIGH_SCREEN_DIR,
    _prior_paths as _prior_screen_paths,
)


SCHEMA_VERSION = "1.0"
DEFAULT_TERRA_HIGH_DATASET_DIR = (
    Path(__file__).with_name("datasets") / "terra_high_cycle"
)
COUNTS = dict(LUNA_LOW_COUNTS)
ERROR_DISTRIBUTION = dict(LUNA_LOW_ERROR_DISTRIBUTION)
SPLITS: dict[str, dict[str, object]] = {
    "terra_high_calibration": {
        "seed": 20260824,
        "model_inputs": "calibration_model_inputs.jsonl",
        "truth": "calibration_truth.jsonl",
        "permitted_use": "one Terra-high calibration run",
    },
    "terra_high_validation": {
        "seed": 20260825,
        "model_inputs": "validation_model_inputs.jsonl",
        "truth": "validation_truth.jsonl",
        "permitted_use": (
            "one frozen Terra-high validation run after passing calibration"
        ),
    },
}


def build_terra_high_cycle_rows() -> dict[
    str,
    tuple[list[dict[str, object]], list[dict[str, object]]],
]:
    datasets = {}
    for split, config in SPLITS.items():
        seed = int(config["seed"])
        source = generate_balanced_wbs_cases(seed=seed)
        rows = build_ai_qa_split_from_clean_cases(
            source_cases=source,
            seed=seed,
            counts=COUNTS,
            error_distribution=ERROR_DISTRIBUTION,
        )
        verify_ai_qa_split_rows(
            split_name=split,
            input_rows=rows[0],
            truth_rows=rows[1],
            expected_counts=COUNTS,
            expected_distribution=ERROR_DISTRIBUTION,
        )
        _verify_semantic_balance(*rows)
        datasets[split] = rows
    return datasets


def _prior_paths() -> dict[str, Path]:
    paths = {
        f"{path.parent.name}_{path.stem}": path
        for path in _prior_screen_paths()
    }
    paths["terra_high_reasoning_screen"] = (
        DEFAULT_TERRA_HIGH_SCREEN_DIR / "model_inputs.jsonl"
    )
    return paths


def _verify_isolation(
    datasets: Mapping[
        str,
        tuple[
            Sequence[Mapping[str, object]],
            Sequence[Mapping[str, object]],
        ],
    ],
) -> dict[str, int]:
    generated = {
        split: {_signature(row) for row in rows[0]}
        for split, rows in datasets.items()
    }
    calibration = generated["terra_high_calibration"]
    validation = generated["terra_high_validation"]
    overlaps = {"calibration_validation": len(calibration & validation)}
    for name, path in _prior_paths().items():
        prior = {_signature(row) for row in _read_jsonl(path)}
        overlaps[f"calibration_{name}"] = len(calibration & prior)
        overlaps[f"validation_{name}"] = len(validation & prior)
    if any(overlaps.values()):
        raise ValueError(f"Terra-high dataset overlap: {overlaps}")
    return overlaps


def write_terra_high_cycle(
    output_dir: Path = DEFAULT_TERRA_HIGH_DATASET_DIR,
) -> dict[str, object]:
    expected_files = {
        "dataset_manifest.json",
        *(
            str(config[key])
            for config in SPLITS.values()
            for key in ("model_inputs", "truth")
        ),
    }
    if any((output_dir / name).exists() for name in expected_files):
        raise FileExistsError("Terra-high cycle artifacts already exist")
    datasets = build_terra_high_cycle_rows()
    overlaps = _verify_isolation(datasets)
    output_dir.mkdir(parents=True, exist_ok=True)
    split_manifest = {}
    for split, (inputs, truth) in datasets.items():
        config = SPLITS[split]
        input_path = output_dir / str(config["model_inputs"])
        truth_path = output_dir / str(config["truth"])
        input_path.write_text(
            "".join(f"{_canonical_json(row)}\n" for row in inputs),
            encoding="utf-8",
        )
        truth_path.write_text(
            "".join(f"{_canonical_json(row)}\n" for row in truth),
            encoding="utf-8",
        )
        split_manifest[split] = {
            "seed": config["seed"],
            "counts": {**COUNTS, "total": sum(COUNTS.values())},
            "error_distribution": ERROR_DISTRIBUTION,
            "wbs_semantic_balance": _verify_semantic_balance(inputs, truth),
            "permitted_use": config["permitted_use"],
            "artifacts": {
                "model_inputs": _artifact_entry(
                    input_path,
                    lines=len(inputs),
                ),
                "truth": _artifact_entry(truth_path, lines=len(truth)),
            },
        }
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "experiment": "synthetic offline Terra-high calibration cycle",
        "hypothesis": (
            "Terra-v1 with high reasoning preserves the paired rooms gain "
            "on independent balanced calibration data."
        ),
        "configuration": {
            "model": "gpt-5.6-terra",
            "reasoning_effort": "high",
            "prompt_version": "terra-v1",
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
            "development_screen_reused": False,
            "consumed_validation_reused": False,
            "validation_requires_passing_calibration_freeze": True,
            "validation_authorized_now": False,
            "locked_holdout_used_for_inference": False,
            "locked_holdout_truth_read": False,
            "openai_called_during_generation": False,
            "product_runtime_modified": False,
            "sol_authorized": False,
        },
    }
    manifest_path = output_dir / "dataset_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    verify_terra_high_cycle(output_dir)
    return manifest


def verify_terra_high_cycle(
    output_dir: Path = DEFAULT_TERRA_HIGH_DATASET_DIR,
) -> dict[str, object]:
    manifest = json.loads(
        (output_dir / "dataset_manifest.json").read_text(encoding="utf-8")
    )
    datasets = {}
    for split in SPLITS:
        entry = manifest["splits"][split]
        input_path = output_dir / entry["artifacts"]["model_inputs"]["file"]
        truth_path = output_dir / entry["artifacts"]["truth"]["file"]
        if (
            _sha256_file(input_path)
            != entry["artifacts"]["model_inputs"]["sha256"]
        ):
            raise ValueError(f"{split} input hash mismatch")
        if _sha256_file(truth_path) != entry["artifacts"]["truth"]["sha256"]:
            raise ValueError(f"{split} truth hash mismatch")
        rows = (_read_jsonl(input_path), _read_jsonl(truth_path))
        verify_ai_qa_split_rows(
            split_name=split,
            input_rows=rows[0],
            truth_rows=rows[1],
            expected_counts=COUNTS,
            expected_distribution=ERROR_DISTRIBUTION,
        )
        if _verify_semantic_balance(*rows) != entry["wbs_semantic_balance"]:
            raise ValueError(f"{split} WBS balance mismatch")
        datasets[split] = rows
    if _verify_isolation(datasets) != manifest["isolation"]["overlaps"]:
        raise ValueError("Terra-high isolation metadata mismatch")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate independent Terra-high calibration data.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_TERRA_HIGH_DATASET_DIR,
    )
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    manifest = (
        verify_terra_high_cycle(args.output_dir)
        if args.verify_only
        else write_terra_high_cycle(args.output_dir)
    )
    print(
        json.dumps(
            {
                "configuration": manifest["configuration"],
                "splits": {
                    name: {
                        "seed": value["seed"],
                        "counts": value["counts"],
                        "input_sha256": value["artifacts"]["model_inputs"][
                            "sha256"
                        ],
                        "truth_sha256": value["artifacts"]["truth"]["sha256"],
                    }
                    for name, value in manifest["splits"].items()
                },
                "overlaps": manifest["isolation"]["overlaps"],
                "boundaries": manifest["boundaries"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
