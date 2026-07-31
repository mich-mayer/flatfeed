from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from eval.ai_qa_clean_generator import (
    CleanAIQACase,
    generate_clean_ai_qa_cases,
)
from eval.ai_qa_datasets import (
    build_ai_qa_split_from_clean_cases,
    verify_ai_qa_split_rows,
)


SCHEMA_VERSION = "1.0"
DEVELOPMENT_SEED = 20260901
SPLIT_NAME = "review_v1_development"

DATASETS_ROOT = Path(__file__).with_name("datasets")
DEFAULT_OUTPUT_DIR = DATASETS_ROOT / SPLIT_NAME
MODEL_INPUTS_FILE = "model_inputs.jsonl"
TRUTH_FILE = "truth.jsonl"
MANIFEST_FILE = "dataset_manifest.json"

COUNTS = {
    "clean": 50,
    "corrupted": 70,
}
ERROR_DISTRIBUTION = {
    "wbs": 10,
    "rent_kalt": 10,
    "rooms": 20,
    "address_postal_code": 10,
    "district": 8,
    "floor": 6,
    "rent_warm": 6,
}


def _derived_seed(seed: int, namespace: str) -> int:
    payload = f"{seed}:{namespace}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as artifact:
        for chunk in iter(lambda: artifact.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_jsonl(
    path: Path,
    rows: Iterable[Mapping[str, object]],
) -> None:
    path.write_text(
        "".join(f"{_canonical_json(row)}\n" for row in rows),
        encoding="utf-8",
    )


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
    ]


def _model_input_signature(row: Mapping[str, object]) -> str:
    return _canonical_json(
        {
            "raw_text": row["raw_text"],
            "parser_snapshot": row["parser_snapshot"],
        }
    )


def _prior_model_input_paths(
    *,
    output_dir: Path,
) -> list[Path]:
    current_input = (output_dir / MODEL_INPUTS_FILE).resolve()
    return [
        path
        for path in sorted(DATASETS_ROOT.rglob("*model_inputs.jsonl"))
        if path.resolve() != current_input
    ]


def _verify_isolation(
    input_rows: Sequence[Mapping[str, object]],
    *,
    output_dir: Path,
) -> dict[str, object]:
    current_signatures = {
        _model_input_signature(row)
        for row in input_rows
    }
    current_raw_texts = {
        str(row["raw_text"])
        for row in input_rows
    }
    current_case_ids = {
        str(row["case_id"])
        for row in input_rows
    }

    overlaps: dict[str, dict[str, int]] = {}
    for path in _prior_model_input_paths(output_dir=output_dir):
        prior_rows = _read_jsonl(path)
        overlaps[str(path.relative_to(DATASETS_ROOT))] = {
            "model_input": len(
                current_signatures
                & {_model_input_signature(row) for row in prior_rows}
            ),
            "raw_text": len(
                current_raw_texts
                & {str(row["raw_text"]) for row in prior_rows}
            ),
            "case_id": len(
                current_case_ids
                & {str(row["case_id"]) for row in prior_rows}
            ),
        }

    if any(
        count
        for categories in overlaps.values()
        for count in categories.values()
    ):
        raise ValueError(
            "review-v1 development data overlaps a prior model-input artifact"
        )

    return {
        "comparison_basis": [
            "raw_text plus parser_snapshot",
            "raw_text",
            "case_id",
        ],
        "prior_artifact_count": len(overlaps),
        "overlaps": overlaps,
    }


def _source_composition(
    source_cases: Sequence[CleanAIQACase],
) -> dict[str, object]:
    return {
        "format_variants": dict(
            sorted(Counter(case.format_variant for case in source_cases).items())
        ),
        "districts": dict(
            sorted(
                Counter(
                    case.parser_snapshot.district
                    for case in source_cases
                ).items()
            )
        ),
        "rooms": dict(
            sorted(
                Counter(
                    str(case.parser_snapshot.rooms)
                    for case in source_cases
                ).items()
            )
        ),
        "wbs_values": dict(
            sorted(
                Counter(
                    case.parser_snapshot.display_wbs
                    for case in source_cases
                ).items()
            )
        ),
    }


def _corruption_composition(
    truth_rows: Sequence[Mapping[str, object]],
) -> dict[str, int]:
    return dict(
        sorted(
            Counter(
                str(row["corruption_type"])
                for row in truth_rows
                if row["case_type"] == "corrupted"
            ).items()
        )
    )


def build_review_development_rows(
    *,
    seed: int = DEVELOPMENT_SEED,
) -> tuple[
    list[dict[str, object]],
    list[dict[str, object]],
    dict[str, object],
]:
    """Build the fresh 120-case development dataset without an API call."""

    if isinstance(seed, bool) or not isinstance(seed, int):
        raise TypeError("seed must be an integer")

    source_cases = generate_clean_ai_qa_cases(
        count=sum(COUNTS.values()),
        seed=_derived_seed(seed, "review-v1-source-cases"),
    )
    input_rows, truth_rows = build_ai_qa_split_from_clean_cases(
        source_cases=source_cases,
        seed=seed,
        counts=COUNTS,
        error_distribution=ERROR_DISTRIBUTION,
    )
    verify_ai_qa_split_rows(
        split_name=SPLIT_NAME,
        input_rows=input_rows,
        truth_rows=truth_rows,
        expected_counts=COUNTS,
        expected_distribution=ERROR_DISTRIBUTION,
    )
    composition = {
        "source": _source_composition(source_cases),
        "corruption_types": _corruption_composition(truth_rows),
    }
    return input_rows, truth_rows, composition


def _artifact_entry(path: Path, *, lines: int) -> dict[str, object]:
    return {
        "bytes": path.stat().st_size,
        "file": path.name,
        "lines": lines,
        "sha256": _sha256_file(path),
    }


def write_review_development(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, object]:
    artifact_paths = [
        output_dir / MODEL_INPUTS_FILE,
        output_dir / TRUTH_FILE,
        output_dir / MANIFEST_FILE,
    ]
    if any(path.exists() for path in artifact_paths):
        raise FileExistsError("review-v1 development artifacts already exist")

    input_rows, truth_rows, composition = build_review_development_rows()
    isolation = _verify_isolation(input_rows, output_dir=output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)
    input_path, truth_path, manifest_path = artifact_paths
    _write_jsonl(input_path, input_rows)
    _write_jsonl(truth_path, truth_rows)

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "experiment": "synthetic offline AI QA review-contract development",
        "purpose": (
            "Develop and compare an evidence-grounded admin-review output "
            "contract before any new final 600-case evaluation."
        ),
        "seed": DEVELOPMENT_SEED,
        "derived_seeds": {
            "source_cases": _derived_seed(
                DEVELOPMENT_SEED,
                "review-v1-source-cases",
            ),
        },
        "split": SPLIT_NAME,
        "counts": {
            **COUNTS,
            "total": sum(COUNTS.values()),
        },
        "error_distribution": ERROR_DISTRIBUTION,
        "composition": composition,
        "model_inputs": _artifact_entry(input_path, lines=len(input_rows)),
        "truth": _artifact_entry(truth_path, lines=len(truth_rows)),
        "isolation": isolation,
        "planned_comparison": {
            "same_cases_for_both_profiles": True,
            "baseline": {
                "model": "gpt-5.6-terra",
                "prompt_version": "terra-v1",
                "reasoning_effort": "high",
            },
            "candidate": {
                "model": "gpt-5.6-terra",
                "prompt_version": "review-v1",
                "reasoning_effort": "high",
            },
        },
        "boundaries": {
            "development_only": True,
            "final_600_case_evidence": False,
            "prior_cases_reused": False,
            "openai_called_during_generation": False,
            "api_execution_authorized_by_manifest": False,
            "product_runtime_modified": False,
            "hidden_truth_separate_from_model_inputs": True,
        },
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    verify_review_development(output_dir)
    return manifest


def verify_review_development(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    manifest_path = output_dir / MANIFEST_FILE
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    input_path = output_dir / str(manifest["model_inputs"]["file"])
    truth_path = output_dir / str(manifest["truth"]["file"])

    if _sha256_file(input_path) != manifest["model_inputs"]["sha256"]:
        raise ValueError("review-v1 model-input hash mismatch")
    if _sha256_file(truth_path) != manifest["truth"]["sha256"]:
        raise ValueError("review-v1 truth hash mismatch")

    input_rows = _read_jsonl(input_path)
    truth_rows = _read_jsonl(truth_path)
    verify_ai_qa_split_rows(
        split_name=SPLIT_NAME,
        input_rows=input_rows,
        truth_rows=truth_rows,
        expected_counts=COUNTS,
        expected_distribution=ERROR_DISTRIBUTION,
    )

    expected_inputs, expected_truth, expected_composition = (
        build_review_development_rows(seed=int(manifest["seed"]))
    )
    if input_rows != expected_inputs or truth_rows != expected_truth:
        raise ValueError("review-v1 artifacts are not reproducible from the seed")
    if manifest["composition"] != expected_composition:
        raise ValueError("review-v1 composition metadata mismatch")

    isolation = _verify_isolation(input_rows, output_dir=output_dir)
    stored_isolation = manifest["isolation"]
    stored_overlaps = stored_isolation["overlaps"]
    current_overlaps = isolation["overlaps"]
    if (
        stored_isolation["comparison_basis"]
        != isolation["comparison_basis"]
        or stored_isolation["prior_artifact_count"]
        != len(stored_overlaps)
        or any(
            current_overlaps.get(path) != counts
            for path, counts in stored_overlaps.items()
        )
    ):
        raise ValueError("review-v1 isolation metadata mismatch")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate the 120-case review-v1 development dataset.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
    )
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()

    manifest = (
        verify_review_development(args.output_dir)
        if args.verify_only
        else write_review_development(args.output_dir)
    )
    print(
        json.dumps(
            {
                "seed": manifest["seed"],
                "counts": manifest["counts"],
                "error_distribution": manifest["error_distribution"],
                "corruption_types": manifest["composition"][
                    "corruption_types"
                ],
                "model_inputs_sha256": manifest["model_inputs"]["sha256"],
                "truth_sha256": manifest["truth"]["sha256"],
                "prior_artifact_count": manifest["isolation"][
                    "prior_artifact_count"
                ],
                "overlaps": manifest["isolation"]["overlaps"],
                "boundaries": manifest["boundaries"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
