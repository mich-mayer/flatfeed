from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from eval.ai_qa_clean_generator import (
    CleanAIQACase,
    generate_clean_ai_qa_cases,
)
from eval.ai_qa_corruptions import (
    MODEL_PARSER_SNAPSHOT_FIELDS,
    OfflineAIQACase,
    build_clean_ai_qa_eval_case,
    generate_controlled_ai_qa_cases,
)


DATASET_SCHEMA_VERSION = "1.0"
DATASET_SEED = 20260722
DEFAULT_DATASET_DIR = Path(__file__).with_name("datasets") / "ai_qa"

DEVELOPMENT_COUNTS = {
    "clean": 50,
    "corrupted": 50,
}
LOCKED_HOLDOUT_COUNTS = {
    "clean": 300,
    "corrupted": 300,
}

# The development distribution approximates the locked holdout proportions
# while ensuring that every supported corruption category is represented.
DEVELOPMENT_ERROR_DISTRIBUTION = {
    "wbs": 13,
    "rent_kalt": 10,
    "rooms": 8,
    "address_postal_code": 7,
    "district": 5,
    "floor": 4,
    "rent_warm": 3,
}
LOCKED_HOLDOUT_ERROR_DISTRIBUTION = {
    "wbs": 75,
    "rent_kalt": 60,
    "rooms": 50,
    "address_postal_code": 40,
    "district": 30,
    "floor": 25,
    "rent_warm": 20,
}

ARTIFACT_FILENAMES = {
    "development_model_inputs": "development_model_inputs.jsonl",
    "development_truth": "development_truth.jsonl",
    "locked_holdout_model_inputs": "locked_holdout_model_inputs.jsonl",
    "locked_holdout_truth": "locked_holdout_truth.jsonl",
    "manifest": "dataset_manifest.json",
}

_MODEL_INPUT_KEYS = {"case_id", "raw_text", "parser_snapshot"}
_PARSER_SNAPSHOT_KEYS = set(MODEL_PARSER_SNAPSHOT_FIELDS)
_TRUTH_KEYS = {
    "case_id",
    "case_type",
    "corrupted_field",
    "expected_value",
    "corrupted_value",
    "corruption_type",
}
_FORBIDDEN_MODEL_INPUT_KEYS = {
    "answer_key",
    "case_type",
    "clean",
    "corrupted",
    "corrupted_field",
    "corrupted_value",
    "corruption_type",
    "error_category",
    "expected_value",
    "format_variant",
    "generation_seed",
    "label",
    "seed",
    "split",
    "title",
    "truth",
}
_OPAQUE_CASE_ID_RE = re.compile(r"^aqa-[0-9a-f]{20}$")
_SNAPSHOT_FIELD_TO_ERROR_CATEGORY = {
    "display_wbs": "wbs",
    "rent_kalt": "rent_kalt",
    "rooms": "rooms",
    "address": "address_postal_code",
    "postal_code": "address_postal_code",
    "district": "district",
    "floor": "floor",
    "rent_warm": "rent_warm",
}
_DISPLAY_ERROR_CATEGORY = {
    "wbs": "WBS",
    "rent_kalt": "Kaltmiete",
    "rooms": "rooms",
    "address_postal_code": "address/postal code",
    "district": "district",
    "floor": "floor",
    "rent_warm": "Warmmiete",
}


def _derived_seed(dataset_seed: int, namespace: str) -> int:
    payload = f"{dataset_seed}:{namespace}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _opaque_case_id(model_payload: Mapping[str, object]) -> str:
    digest = hashlib.sha256(
        _canonical_json(model_payload).encode("utf-8")
    ).hexdigest()
    return f"aqa-{digest[:20]}"


def _expand_distribution(
    distribution: Mapping[str, int],
    *,
    seed: int,
) -> list[str]:
    fields = [
        field
        for field, count in distribution.items()
        for _ in range(count)
    ]
    random.Random(seed).shuffle(fields)
    return fields


def _case_rows(
    cases: Sequence[OfflineAIQACase],
    *,
    order_seed: int,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    paired_rows: list[tuple[dict[str, object], dict[str, object]]] = []
    for case in cases:
        model_payload = case.model_input.as_dict()
        case_id = _opaque_case_id(model_payload)
        input_row = {
            "case_id": case_id,
            **model_payload,
        }
        truth_row = {
            **case.answer_key.as_dict(),
            "case_id": case_id,
        }
        paired_rows.append((input_row, truth_row))

    random.Random(order_seed).shuffle(paired_rows)
    return (
        [input_row for input_row, _ in paired_rows],
        [truth_row for _, truth_row in paired_rows],
    )


def _build_split(
    *,
    clean_source_cases: Sequence[Any],
    corrupted_source_cases: Sequence[Any],
    error_distribution: Mapping[str, int],
    corruption_field_seed: int,
    corruption_value_seed: int,
    order_seed: int,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    if len(corrupted_source_cases) != sum(error_distribution.values()):
        raise ValueError("corrupted source count must match the error distribution")

    clean_cases = [
        build_clean_ai_qa_eval_case(clean_case)
        for clean_case in clean_source_cases
    ]
    corruption_fields = _expand_distribution(
        error_distribution,
        seed=corruption_field_seed,
    )
    corrupted_cases = generate_controlled_ai_qa_cases(
        corrupted_source_cases,
        corruption_fields=corruption_fields,
        seed=corruption_value_seed,
    )
    return _case_rows(
        [*clean_cases, *corrupted_cases],
        order_seed=order_seed,
    )


def build_ai_qa_dataset_rows(
    *,
    seed: int = DATASET_SEED,
) -> dict[str, tuple[list[dict[str, object]], list[dict[str, object]]]]:
    """Build both offline AI QA splits in memory without calling a model."""

    if isinstance(seed, bool) or not isinstance(seed, int):
        raise TypeError("seed must be an integer")

    total_source_cases = (
        sum(DEVELOPMENT_COUNTS.values())
        + sum(LOCKED_HOLDOUT_COUNTS.values())
    )
    source_cases = generate_clean_ai_qa_cases(
        count=total_source_cases,
        seed=_derived_seed(seed, "clean-source-cases"),
    )

    development_source_end = sum(DEVELOPMENT_COUNTS.values())
    development_sources = source_cases[:development_source_end]
    holdout_sources = source_cases[development_source_end:]

    development_clean_end = DEVELOPMENT_COUNTS["clean"]
    holdout_clean_end = LOCKED_HOLDOUT_COUNTS["clean"]

    development = _build_split(
        clean_source_cases=development_sources[:development_clean_end],
        corrupted_source_cases=development_sources[development_clean_end:],
        error_distribution=DEVELOPMENT_ERROR_DISTRIBUTION,
        corruption_field_seed=_derived_seed(seed, "development-field-order"),
        corruption_value_seed=_derived_seed(seed, "development-corruptions"),
        order_seed=_derived_seed(seed, "development-row-order"),
    )
    locked_holdout = _build_split(
        clean_source_cases=holdout_sources[:holdout_clean_end],
        corrupted_source_cases=holdout_sources[holdout_clean_end:],
        error_distribution=LOCKED_HOLDOUT_ERROR_DISTRIBUTION,
        corruption_field_seed=_derived_seed(seed, "holdout-field-order"),
        corruption_value_seed=_derived_seed(seed, "holdout-corruptions"),
        order_seed=_derived_seed(seed, "holdout-row-order"),
    )
    return {
        "development": development,
        "locked_holdout": locked_holdout,
    }


def build_ai_qa_custom_split(
    *,
    seed: int,
    counts: Mapping[str, int],
    error_distribution: Mapping[str, int],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Build one deterministic split with an explicit predeclared contract."""

    if isinstance(seed, bool) or not isinstance(seed, int):
        raise TypeError("seed must be an integer")
    if set(counts) != {"clean", "corrupted"}:
        raise ValueError("counts must contain clean and corrupted")
    if any(
        isinstance(value, bool)
        or not isinstance(value, int)
        or value <= 0
        for value in counts.values()
    ):
        raise ValueError("custom split counts must be positive integers")
    if set(error_distribution) != set(LOCKED_HOLDOUT_ERROR_DISTRIBUTION):
        raise ValueError("custom split error distribution fields are invalid")
    if any(
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 0
        for value in error_distribution.values()
    ):
        raise ValueError("custom split distribution values must be non-negative")
    if sum(error_distribution.values()) != counts["corrupted"]:
        raise ValueError("custom split distribution must match corrupted count")

    source_cases = generate_clean_ai_qa_cases(
        count=sum(counts.values()),
        seed=_derived_seed(seed, "custom-clean-source-cases"),
    )
    return build_ai_qa_split_from_clean_cases(
        source_cases=source_cases,
        seed=seed,
        counts=counts,
        error_distribution=error_distribution,
    )


def build_ai_qa_split_from_clean_cases(
    *,
    source_cases: Sequence[CleanAIQACase],
    seed: int,
    counts: Mapping[str, int],
    error_distribution: Mapping[str, int],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Build a verified split from pre-generated clean source cases.

    Specialized eval cycles may vary the visible listing language while
    reusing the same single-error corruption and leakage contracts.
    """

    expected_source_count = sum(counts.values())
    if len(source_cases) != expected_source_count:
        raise ValueError(
            "source case count must match clean plus corrupted counts"
        )
    input_rows, truth_rows = _build_split(
        clean_source_cases=source_cases[: counts["clean"]],
        corrupted_source_cases=source_cases[counts["clean"] :],
        error_distribution=error_distribution,
        corruption_field_seed=_derived_seed(seed, "custom-field-order"),
        corruption_value_seed=_derived_seed(seed, "custom-corruptions"),
        order_seed=_derived_seed(seed, "custom-row-order"),
    )
    verify_ai_qa_split_rows(
        split_name="custom",
        input_rows=input_rows,
        truth_rows=truth_rows,
        expected_counts=counts,
        expected_distribution=error_distribution,
    )
    return input_rows, truth_rows


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, object]]) -> None:
    serialized = "".join(f"{_canonical_json(row)}\n" for row in rows)
    path.write_text(serialized, encoding="utf-8")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as artifact:
        for chunk in iter(lambda: artifact.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _display_distribution(
    distribution: Mapping[str, int],
) -> dict[str, int]:
    return {
        _DISPLAY_ERROR_CATEGORY[field]: count
        for field, count in distribution.items()
    }


def _artifact_manifest_entry(
    *,
    path: Path,
    lines: int,
) -> dict[str, object]:
    return {
        "bytes": path.stat().st_size,
        "file": path.name,
        "lines": lines,
        "sha256": _sha256_file(path),
    }


def _manifest(
    *,
    output_dir: Path,
    seed: int,
    datasets: Mapping[
        str,
        tuple[Sequence[Mapping[str, object]], Sequence[Mapping[str, object]]],
    ],
) -> dict[str, object]:
    development_inputs, development_truth = datasets["development"]
    holdout_inputs, holdout_truth = datasets["locked_holdout"]

    development_input_path = (
        output_dir / ARTIFACT_FILENAMES["development_model_inputs"]
    )
    development_truth_path = output_dir / ARTIFACT_FILENAMES["development_truth"]
    holdout_input_path = (
        output_dir / ARTIFACT_FILENAMES["locked_holdout_model_inputs"]
    )
    holdout_truth_path = (
        output_dir / ARTIFACT_FILENAMES["locked_holdout_truth"]
    )

    return {
        "schema_version": DATASET_SCHEMA_VERSION,
        "experiment": "synthetic offline AI QA evaluation",
        "hash_algorithm": "SHA-256",
        "serialization": {
            "encoding": "UTF-8",
            "format": "JSON Lines",
            "json_keys": "sorted",
            "line_ending": "LF",
        },
        "seeds": {
            "dataset": seed,
            "clean_source_cases": _derived_seed(seed, "clean-source-cases"),
            "development_field_order": _derived_seed(
                seed,
                "development-field-order",
            ),
            "development_corruptions": _derived_seed(
                seed,
                "development-corruptions",
            ),
            "development_row_order": _derived_seed(
                seed,
                "development-row-order",
            ),
            "locked_holdout_field_order": _derived_seed(
                seed,
                "holdout-field-order",
            ),
            "locked_holdout_corruptions": _derived_seed(
                seed,
                "holdout-corruptions",
            ),
            "locked_holdout_row_order": _derived_seed(
                seed,
                "holdout-row-order",
            ),
        },
        "splits": {
            "development": {
                "counts": {
                    **DEVELOPMENT_COUNTS,
                    "total": sum(DEVELOPMENT_COUNTS.values()),
                },
                "error_distribution": _display_distribution(
                    DEVELOPMENT_ERROR_DISTRIBUTION
                ),
                "artifacts": {
                    "model_inputs": _artifact_manifest_entry(
                        path=development_input_path,
                        lines=len(development_inputs),
                    ),
                    "truth": _artifact_manifest_entry(
                        path=development_truth_path,
                        lines=len(development_truth),
                    ),
                },
            },
            "locked_holdout": {
                "locked": True,
                "permitted_use": "one frozen final evaluation only",
                "counts": {
                    **LOCKED_HOLDOUT_COUNTS,
                    "total": sum(LOCKED_HOLDOUT_COUNTS.values()),
                },
                "error_distribution": _display_distribution(
                    LOCKED_HOLDOUT_ERROR_DISTRIBUTION
                ),
                "artifacts": {
                    "model_inputs": _artifact_manifest_entry(
                        path=holdout_input_path,
                        lines=len(holdout_inputs),
                    ),
                    "truth": _artifact_manifest_entry(
                        path=holdout_truth_path,
                        lines=len(holdout_truth),
                    ),
                },
            },
        },
        "global_counts": {
            "cases": len(development_inputs) + len(holdout_inputs),
            "unique_case_ids": len(
                {
                    row["case_id"]
                    for row in [*development_inputs, *holdout_inputs]
                }
            ),
            "unique_raw_texts": len(
                {
                    row["raw_text"]
                    for row in [*development_inputs, *holdout_inputs]
                }
            ),
            "development_holdout_overlap": 0,
        },
    }


def write_ai_qa_datasets(
    output_dir: Path = DEFAULT_DATASET_DIR,
    *,
    seed: int = DATASET_SEED,
) -> dict[str, object]:
    """Write deterministic model-input, truth, and manifest artifacts."""

    datasets = build_ai_qa_dataset_rows(seed=seed)
    output_dir.mkdir(parents=True, exist_ok=True)

    development_inputs, development_truth = datasets["development"]
    holdout_inputs, holdout_truth = datasets["locked_holdout"]
    _write_jsonl(
        output_dir / ARTIFACT_FILENAMES["development_model_inputs"],
        development_inputs,
    )
    _write_jsonl(
        output_dir / ARTIFACT_FILENAMES["development_truth"],
        development_truth,
    )
    _write_jsonl(
        output_dir / ARTIFACT_FILENAMES["locked_holdout_model_inputs"],
        holdout_inputs,
    )
    _write_jsonl(
        output_dir / ARTIFACT_FILENAMES["locked_holdout_truth"],
        holdout_truth,
    )

    manifest = _manifest(
        output_dir=output_dir,
        seed=seed,
        datasets=datasets,
    )
    manifest_path = output_dir / ARTIFACT_FILENAMES["manifest"]
    manifest_path.write_text(
        f"{json.dumps(manifest, ensure_ascii=False, indent=2)}\n",
        encoding="utf-8",
    )
    verify_ai_qa_dataset(output_dir)
    return manifest


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as artifact:
        for line_number, line in enumerate(artifact, start=1):
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"{path.name}:{line_number} is not valid JSON"
                ) from exc
            if not isinstance(row, dict):
                raise ValueError(f"{path.name}:{line_number} must be a JSON object")
            rows.append(row)
    return rows


def _all_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {
            nested_key
            for nested_value in value.values()
            for nested_key in _all_keys(nested_value)
        }
    if isinstance(value, list):
        return {
            nested_key
            for nested_value in value
            for nested_key in _all_keys(nested_value)
        }
    return set()


def _validate_model_input_row(
    row: Mapping[str, Any],
    *,
    artifact_name: str,
) -> None:
    if set(row) != _MODEL_INPUT_KEYS:
        raise ValueError(
            f"{artifact_name} model input keys must be "
            f"{sorted(_MODEL_INPUT_KEYS)}"
        )
    if not isinstance(row["case_id"], str) or _OPAQUE_CASE_ID_RE.fullmatch(
        row["case_id"]
    ) is None:
        raise ValueError(f"{artifact_name} contains a non-opaque case_id")
    if not isinstance(row["raw_text"], str) or not row["raw_text"].strip():
        raise ValueError(f"{artifact_name} contains an empty raw_text")
    if row["case_id"] in row["raw_text"]:
        raise ValueError(f"{artifact_name} leaks case_id into raw_text")

    snapshot = row["parser_snapshot"]
    if not isinstance(snapshot, dict) or set(snapshot) != _PARSER_SNAPSHOT_KEYS:
        raise ValueError(
            f"{artifact_name} parser_snapshot keys must be "
            f"{sorted(_PARSER_SNAPSHOT_KEYS)}"
        )
    leaked_keys = _all_keys(row) & _FORBIDDEN_MODEL_INPUT_KEYS
    if leaked_keys:
        raise ValueError(
            f"{artifact_name} contains answer-key leakage: "
            f"{sorted(leaked_keys)}"
        )
    expected_case_id = _opaque_case_id(
        {
            "raw_text": row["raw_text"],
            "parser_snapshot": snapshot,
        }
    )
    if row["case_id"] != expected_case_id:
        raise ValueError(f"{artifact_name} case_id does not match model input")


def _validate_truth_row(
    row: Mapping[str, Any],
    *,
    artifact_name: str,
) -> None:
    if set(row) != _TRUTH_KEYS:
        raise ValueError(
            f"{artifact_name} truth keys must be {sorted(_TRUTH_KEYS)}"
        )
    if not isinstance(row["case_id"], str) or _OPAQUE_CASE_ID_RE.fullmatch(
        row["case_id"]
    ) is None:
        raise ValueError(f"{artifact_name} contains a non-opaque case_id")
    if row["case_type"] not in {"clean", "corrupted"}:
        raise ValueError(f"{artifact_name} contains an invalid case_type")

    if row["case_type"] == "clean":
        hidden_values = (
            row["corrupted_field"],
            row["expected_value"],
            row["corrupted_value"],
            row["corruption_type"],
        )
        if any(value is not None for value in hidden_values):
            raise ValueError(f"{artifact_name} clean truth must have no corruption")
        return

    corrupted_field = row["corrupted_field"]
    if corrupted_field not in _SNAPSHOT_FIELD_TO_ERROR_CATEGORY:
        raise ValueError(
            f"{artifact_name} contains an unsupported corrupted_field"
        )
    if row["expected_value"] == row["corrupted_value"]:
        raise ValueError(
            f"{artifact_name} corruption must change the expected value"
        )
    if not isinstance(row["corruption_type"], str) or not row[
        "corruption_type"
    ].strip():
        raise ValueError(f"{artifact_name} corrupted truth needs a type")


def _input_signature(row: Mapping[str, Any]) -> str:
    return _canonical_json(
        {
            "raw_text": row["raw_text"],
            "parser_snapshot": row["parser_snapshot"],
        }
    )


def _actual_error_distribution(
    truth_rows: Sequence[Mapping[str, Any]],
) -> dict[str, int]:
    distribution = {
        field: 0
        for field in LOCKED_HOLDOUT_ERROR_DISTRIBUTION
    }
    for row in truth_rows:
        if row["case_type"] != "corrupted":
            continue
        category = _SNAPSHOT_FIELD_TO_ERROR_CATEGORY[row["corrupted_field"]]
        distribution[category] += 1
    return distribution


def _verify_split(
    *,
    split_name: str,
    input_rows: Sequence[Mapping[str, Any]],
    truth_rows: Sequence[Mapping[str, Any]],
    expected_counts: Mapping[str, int],
    expected_distribution: Mapping[str, int],
) -> None:
    for row in input_rows:
        _validate_model_input_row(row, artifact_name=split_name)
    for row in truth_rows:
        _validate_truth_row(row, artifact_name=split_name)

    if len(input_rows) != sum(expected_counts.values()):
        raise ValueError(f"{split_name} has the wrong model-input count")
    if len(truth_rows) != len(input_rows):
        raise ValueError(f"{split_name} model-input and truth counts differ")

    input_ids = [row["case_id"] for row in input_rows]
    truth_ids = [row["case_id"] for row in truth_rows]
    if input_ids != truth_ids:
        raise ValueError(f"{split_name} model-input and truth row order differs")
    if len(set(input_ids)) != len(input_ids):
        raise ValueError(f"{split_name} contains duplicate case IDs")
    for input_row, truth_row in zip(input_rows, truth_rows):
        if truth_row["case_type"] != "corrupted":
            continue
        corrupted_field = truth_row["corrupted_field"]
        snapshot = input_row["parser_snapshot"]
        if snapshot[corrupted_field] != truth_row["corrupted_value"]:
            raise ValueError(
                f"{split_name} truth does not match the corrupted model input"
            )

    actual_counts = {
        case_type: sum(
            row["case_type"] == case_type
            for row in truth_rows
        )
        for case_type in ("clean", "corrupted")
    }
    if actual_counts != dict(expected_counts):
        raise ValueError(f"{split_name} has the wrong clean/corrupted counts")
    if _actual_error_distribution(truth_rows) != dict(expected_distribution):
        raise ValueError(f"{split_name} has the wrong error distribution")

    raw_texts = [row["raw_text"] for row in input_rows]
    if len(set(raw_texts)) != len(raw_texts):
        raise ValueError(f"{split_name} contains duplicate listings")
    signatures = [_input_signature(row) for row in input_rows]
    if len(set(signatures)) != len(signatures):
        raise ValueError(f"{split_name} contains duplicate model inputs")


def verify_ai_qa_split_rows(
    *,
    split_name: str,
    input_rows: Sequence[Mapping[str, Any]],
    truth_rows: Sequence[Mapping[str, Any]],
    expected_counts: Mapping[str, int] = DEVELOPMENT_COUNTS,
    expected_distribution: Mapping[str, int] = DEVELOPMENT_ERROR_DISTRIBUTION,
) -> None:
    """Validate a development-sized split without writing dataset artifacts."""

    _verify_split(
        split_name=split_name,
        input_rows=input_rows,
        truth_rows=truth_rows,
        expected_counts=expected_counts,
        expected_distribution=expected_distribution,
    )


def _manifest_artifact(
    manifest: Mapping[str, Any],
    *,
    split_name: str,
    artifact_type: str,
) -> Mapping[str, Any]:
    return manifest["splits"][split_name]["artifacts"][artifact_type]


def verify_ai_qa_dataset(
    output_dir: Path = DEFAULT_DATASET_DIR,
) -> dict[str, object]:
    """Verify counts, distribution, uniqueness, isolation, and file hashes."""

    manifest_path = output_dir / ARTIFACT_FILENAMES["manifest"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != DATASET_SCHEMA_VERSION:
        raise ValueError("manifest schema_version is incorrect")
    if manifest.get("experiment") != "synthetic offline AI QA evaluation":
        raise ValueError("manifest experiment label is incorrect")
    if manifest.get("hash_algorithm") != "SHA-256":
        raise ValueError("manifest hash algorithm is incorrect")
    if manifest.get("serialization") != {
        "encoding": "UTF-8",
        "format": "JSON Lines",
        "json_keys": "sorted",
        "line_ending": "LF",
    }:
        raise ValueError("manifest serialization contract is incorrect")

    dataset_seed = manifest.get("seeds", {}).get("dataset")
    if isinstance(dataset_seed, bool) or not isinstance(dataset_seed, int):
        raise ValueError("manifest dataset seed is invalid")
    expected_seeds = {
        "dataset": dataset_seed,
        "clean_source_cases": _derived_seed(
            dataset_seed,
            "clean-source-cases",
        ),
        "development_field_order": _derived_seed(
            dataset_seed,
            "development-field-order",
        ),
        "development_corruptions": _derived_seed(
            dataset_seed,
            "development-corruptions",
        ),
        "development_row_order": _derived_seed(
            dataset_seed,
            "development-row-order",
        ),
        "locked_holdout_field_order": _derived_seed(
            dataset_seed,
            "holdout-field-order",
        ),
        "locked_holdout_corruptions": _derived_seed(
            dataset_seed,
            "holdout-corruptions",
        ),
        "locked_holdout_row_order": _derived_seed(
            dataset_seed,
            "holdout-row-order",
        ),
    }
    if manifest["seeds"] != expected_seeds:
        raise ValueError("manifest derived seeds are incorrect")
    if manifest.get("splits", {}).get("development", {}).get("counts") != {
        **DEVELOPMENT_COUNTS,
        "total": sum(DEVELOPMENT_COUNTS.values()),
    }:
        raise ValueError("manifest development counts are incorrect")
    if manifest["splits"]["development"].get(
        "error_distribution"
    ) != _display_distribution(DEVELOPMENT_ERROR_DISTRIBUTION):
        raise ValueError("manifest development distribution is incorrect")
    if manifest.get("splits", {}).get("locked_holdout", {}).get("counts") != {
        **LOCKED_HOLDOUT_COUNTS,
        "total": sum(LOCKED_HOLDOUT_COUNTS.values()),
    }:
        raise ValueError("manifest locked holdout counts are incorrect")
    if manifest["splits"]["locked_holdout"].get(
        "error_distribution"
    ) != _display_distribution(LOCKED_HOLDOUT_ERROR_DISTRIBUTION):
        raise ValueError("manifest locked holdout distribution is incorrect")
    if manifest["splits"]["locked_holdout"].get("locked") is not True:
        raise ValueError("manifest locked holdout flag is incorrect")
    if (
        manifest["splits"]["locked_holdout"].get("permitted_use")
        != "one frozen final evaluation only"
    ):
        raise ValueError("manifest locked holdout use is incorrect")

    development_inputs = _read_jsonl(
        output_dir / ARTIFACT_FILENAMES["development_model_inputs"]
    )
    development_truth = _read_jsonl(
        output_dir / ARTIFACT_FILENAMES["development_truth"]
    )
    holdout_inputs = _read_jsonl(
        output_dir / ARTIFACT_FILENAMES["locked_holdout_model_inputs"]
    )
    holdout_truth = _read_jsonl(
        output_dir / ARTIFACT_FILENAMES["locked_holdout_truth"]
    )

    _verify_split(
        split_name="development",
        input_rows=development_inputs,
        truth_rows=development_truth,
        expected_counts=DEVELOPMENT_COUNTS,
        expected_distribution=DEVELOPMENT_ERROR_DISTRIBUTION,
    )
    _verify_split(
        split_name="locked_holdout",
        input_rows=holdout_inputs,
        truth_rows=holdout_truth,
        expected_counts=LOCKED_HOLDOUT_COUNTS,
        expected_distribution=LOCKED_HOLDOUT_ERROR_DISTRIBUTION,
    )

    all_inputs = [*development_inputs, *holdout_inputs]
    all_ids = [row["case_id"] for row in all_inputs]
    all_raw_texts = [row["raw_text"] for row in all_inputs]
    all_signatures = [_input_signature(row) for row in all_inputs]
    if len(set(all_ids)) != len(all_ids):
        raise ValueError("development and holdout case IDs overlap")
    if len(set(all_raw_texts)) != len(all_raw_texts):
        raise ValueError("development and holdout listings overlap")
    if len(set(all_signatures)) != len(all_signatures):
        raise ValueError("development and holdout model inputs overlap")

    artifact_rows = {
        ("development", "model_inputs"): development_inputs,
        ("development", "truth"): development_truth,
        ("locked_holdout", "model_inputs"): holdout_inputs,
        ("locked_holdout", "truth"): holdout_truth,
    }
    for (split_name, artifact_type), rows in artifact_rows.items():
        artifact = _manifest_artifact(
            manifest,
            split_name=split_name,
            artifact_type=artifact_type,
        )
        expected_artifact_key = (
            f"{split_name}_{artifact_type}"
            if split_name == "development"
            else f"locked_holdout_{artifact_type}"
        )
        expected_filename = ARTIFACT_FILENAMES[expected_artifact_key]
        if artifact.get("file") != expected_filename:
            raise ValueError(
                f"{split_name} {artifact_type} filename is incorrect"
            )
        if re.fullmatch(r"[0-9a-f]{64}", str(artifact.get("sha256"))) is None:
            raise ValueError(f"{expected_filename} SHA-256 format is invalid")
        path = output_dir / artifact["file"]
        if artifact["lines"] != len(rows):
            raise ValueError(f"{path.name} line count does not match manifest")
        if artifact.get("bytes") != path.stat().st_size:
            raise ValueError(f"{path.name} byte count does not match manifest")
        if artifact["sha256"] != _sha256_file(path):
            raise ValueError(f"{path.name} SHA-256 does not match manifest")

    if manifest["global_counts"] != {
        "cases": 700,
        "unique_case_ids": 700,
        "unique_raw_texts": 700,
        "development_holdout_overlap": 0,
    }:
        raise ValueError("manifest global counts are incorrect")
    return manifest


def verify_dataset_reproducibility(
    output_dir: Path = DEFAULT_DATASET_DIR,
) -> None:
    """Regenerate all artifacts and require byte-identical output."""

    manifest = verify_ai_qa_dataset(output_dir)
    with tempfile.TemporaryDirectory() as temporary_directory:
        regenerated_dir = Path(temporary_directory)
        write_ai_qa_datasets(
            regenerated_dir,
            seed=manifest["seeds"]["dataset"],
        )
        for filename in ARTIFACT_FILENAMES.values():
            current_bytes = (output_dir / filename).read_bytes()
            regenerated_bytes = (regenerated_dir / filename).read_bytes()
            if current_bytes != regenerated_bytes:
                raise ValueError(f"{filename} is not reproducible")


def public_dataset_summary(manifest: Mapping[str, Any]) -> dict[str, object]:
    """Return aggregate counts and hashes without exposing truth contents."""

    summary: dict[str, object] = {
        "dataset_seed": manifest["seeds"]["dataset"],
        "total_cases": manifest["global_counts"]["cases"],
        "unique_cases": manifest["global_counts"]["unique_case_ids"],
        "development_holdout_overlap": manifest["global_counts"][
            "development_holdout_overlap"
        ],
        "splits": {},
    }
    for split_name in ("development", "locked_holdout"):
        split = manifest["splits"][split_name]
        summary["splits"][split_name] = {
            "counts": split["counts"],
            "error_distribution": split["error_distribution"],
            "model_inputs_sha256": split["artifacts"]["model_inputs"]["sha256"],
            "truth_sha256": split["artifacts"]["truth"]["sha256"],
        }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate or verify offline AI QA JSONL datasets.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_DATASET_DIR,
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Verify existing artifacts without replacing them.",
    )
    args = parser.parse_args()

    if args.check_only:
        manifest = verify_ai_qa_dataset(args.output_dir)
    else:
        manifest = write_ai_qa_datasets(args.output_dir)
    verify_dataset_reproducibility(args.output_dir)
    print(
        json.dumps(
            public_dataset_summary(manifest),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
