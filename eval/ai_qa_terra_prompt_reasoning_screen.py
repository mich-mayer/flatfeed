from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from eval.ai_qa_terra_effort_screen import (
    SCREEN_COUNTS,
    SCREEN_ERROR_DISTRIBUTION,
    SCREEN_MODEL_INPUTS,
    SCREEN_TRUTH,
    _canonical_json,
    _prior_paths,
    _sha256_file,
    _signature,
    _verify_composition,
    build_terra_effort_screen_rows,
)
from eval.ai_qa_datasets import verify_ai_qa_split_rows


SCREEN_SCHEMA_VERSION = "1.0"
SCREEN_SEED = 20260819
SCREEN_SPLIT = "terra_prompt_reasoning_screen"
DEFAULT_TERRA_PROMPT_REASONING_SCREEN_DIR = (
    Path(__file__).with_name("datasets") / "terra_prompt_reasoning_screen"
)
PRIOR_TERRA_INPUT_PATH = (
    Path(__file__).with_name("datasets")
    / "terra_effort_screen"
    / "model_inputs.jsonl"
)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _verify_isolation(input_rows: Sequence[Mapping[str, object]]) -> dict[str, int]:
    current = {_signature(row) for row in input_rows}
    paths = [*_prior_paths(), PRIOR_TERRA_INPUT_PATH]
    overlaps = {
        path.parent.name + "_" + path.stem: len(
            current & {_signature(row) for row in _read_jsonl(path)}
        )
        for path in paths
    }
    if any(overlaps.values()):
        raise ValueError(f"Terra 2x2 screen overlaps prior data: {overlaps}")
    return overlaps


def build_terra_prompt_reasoning_screen_rows() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    return build_terra_effort_screen_rows(seed=SCREEN_SEED)


def write_terra_prompt_reasoning_screen(
    output_dir: Path = DEFAULT_TERRA_PROMPT_REASONING_SCREEN_DIR,
) -> dict[str, object]:
    inputs, truth = build_terra_prompt_reasoning_screen_rows()
    overlaps = _verify_isolation(inputs)
    output_dir.mkdir(parents=True, exist_ok=True)
    input_path = output_dir / SCREEN_MODEL_INPUTS
    truth_path = output_dir / SCREEN_TRUTH
    input_path.write_text("".join(f"{_canonical_json(row)}\n" for row in inputs), encoding="utf-8")
    truth_path.write_text("".join(f"{_canonical_json(row)}\n" for row in truth), encoding="utf-8")
    manifest = {
        "schema_version": SCREEN_SCHEMA_VERSION,
        "experiment": "synthetic offline Terra prompt x reasoning screen",
        "seed": SCREEN_SEED,
        "split": SCREEN_SPLIT,
        "counts": {**SCREEN_COUNTS, "total": sum(SCREEN_COUNTS.values())},
        "error_distribution": SCREEN_ERROR_DISTRIBUTION,
        "composition": _verify_composition(inputs, truth),
        "model_inputs": {"file": input_path.name, "lines": len(inputs), "sha256": _sha256_file(input_path)},
        "truth": {"file": truth_path.name, "lines": len(truth), "sha256": _sha256_file(truth_path)},
        "isolation": {"overlaps": overlaps},
        "profiles": [
            {"id": "luna-v5-low", "prompt_version": "luna-v5", "reasoning_effort": "low"},
            {"id": "terra-v1-low", "prompt_version": "terra-v1", "reasoning_effort": "low"},
            {"id": "luna-v5-medium", "prompt_version": "luna-v5", "reasoning_effort": "medium"},
            {"id": "terra-v1-medium", "prompt_version": "terra-v1", "reasoning_effort": "medium"},
        ],
        "selection_rule": {
            "coverage": 1.0,
            "technical_failures": 0,
            "minimum_correct_wbs": 18,
            "maximum_clean_false_alerts": 1,
            "minimum_correct_non_wbs": 11,
            "minimum_total_correct": 44,
            "tie_break_order": [
                "total_correct_desc",
                "correct_wbs_desc",
                "correct_non_wbs_desc",
                "false_alerts_asc",
                "observed_cost_usd_asc",
                "profile_id_asc",
            ],
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
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    verify_terra_prompt_reasoning_screen(output_dir)
    return manifest


def verify_terra_prompt_reasoning_screen(
    output_dir: Path = DEFAULT_TERRA_PROMPT_REASONING_SCREEN_DIR,
) -> dict[str, object]:
    manifest = json.loads((output_dir / "dataset_manifest.json").read_text(encoding="utf-8"))
    input_path = output_dir / manifest["model_inputs"]["file"]
    truth_path = output_dir / manifest["truth"]["file"]
    if _sha256_file(input_path) != manifest["model_inputs"]["sha256"]:
        raise ValueError("Terra 2x2 input hash mismatch")
    if _sha256_file(truth_path) != manifest["truth"]["sha256"]:
        raise ValueError("Terra 2x2 truth hash mismatch")
    inputs, truth = _read_jsonl(input_path), _read_jsonl(truth_path)
    verify_ai_qa_split_rows(
        split_name=SCREEN_SPLIT,
        input_rows=inputs,
        truth_rows=truth,
        expected_counts=SCREEN_COUNTS,
        expected_distribution=SCREEN_ERROR_DISTRIBUTION,
    )
    if _verify_composition(inputs, truth) != manifest["composition"]:
        raise ValueError("Terra 2x2 composition metadata mismatch")
    if _verify_isolation(inputs) != manifest["isolation"]["overlaps"]:
        raise ValueError("Terra 2x2 isolation metadata mismatch")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Terra prompt x reasoning screen data.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_TERRA_PROMPT_REASONING_SCREEN_DIR)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    manifest = verify_terra_prompt_reasoning_screen(args.output_dir) if args.verify_only else write_terra_prompt_reasoning_screen(args.output_dir)
    print(json.dumps({
        "seed": manifest["seed"],
        "counts": manifest["counts"],
        "model_inputs_sha256": manifest["model_inputs"]["sha256"],
        "truth_sha256": manifest["truth"]["sha256"],
        "overlaps": manifest["isolation"]["overlaps"],
        "profiles": manifest["profiles"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
