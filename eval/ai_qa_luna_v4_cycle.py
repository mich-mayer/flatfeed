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

from eval.ai_qa_clean_generator import (
    CleanAIQACase,
    WBS_TEXTS,
    generate_clean_ai_qa_cases,
)
from eval.ai_qa_datasets import (
    ARTIFACT_FILENAMES,
    DEFAULT_DATASET_DIR,
    build_ai_qa_split_from_clean_cases,
    verify_ai_qa_split_rows,
)
from eval.ai_qa_luna_calibration import DEFAULT_LUNA_DATASET_DIR
from eval.ai_qa_luna_v3_cycle import DEFAULT_LUNA_V3_DATASET_DIR


LUNA_V4_DATASET_SCHEMA_VERSION = "1.0"
LUNA_V4_CALIBRATION_SEED = 20260727
LUNA_V4_VALIDATION_SEED = 20260728
DEFAULT_LUNA_V4_DATASET_DIR = (
    Path(__file__).with_name("datasets") / "luna_v4_cycle"
)

LUNA_V4_COUNTS = {"clean": 120, "corrupted": 120}
LUNA_V4_ERROR_DISTRIBUTION = {
    "wbs": 50,
    "rent_kalt": 20,
    "rooms": 15,
    "address_postal_code": 10,
    "district": 10,
    "floor": 8,
    "rent_warm": 7,
}
LUNA_V4_SPLITS: dict[str, dict[str, object]] = {
    "luna_v4_calibration": {
        "seed": LUNA_V4_CALIBRATION_SEED,
        "model_inputs": "calibration_model_inputs.jsonl",
        "truth": "calibration_truth.jsonl",
        "permitted_use": "one luna-v4 calibration run",
    },
    "luna_v4_validation": {
        "seed": LUNA_V4_VALIDATION_SEED,
        "model_inputs": "validation_model_inputs.jsonl",
        "truth": "validation_truth.jsonl",
        "permitted_use": "one frozen luna-v4 validation run",
    },
}

# Each phrase is an unambiguous semantic equivalent of its parser snapshot.
# Several variants deliberately resemble plausible source-format drift rather
# than the fixed labels used by the base generator.
WBS_SEMANTIC_DRIFT_PHRASES: dict[str, tuple[str, ...]] = {
    "No WBS required": (
        "Die Wohnung wird frei finanziert vermietet; ein WBS ist nicht erforderlich.",
        "Bewerbungen sind ohne Wohnberechtigungsschein möglich.",
        "Für dieses Angebot wird ausdrücklich kein WBS verlangt.",
        "Es handelt sich nicht um eine WBS-gebundene Wohnung.",
        "Eine Anmietung ist unabhängig von einem Wohnberechtigungsschein möglich.",
        "WBS: nicht erforderlich.",
    ),
    "WBS required, type unknown": (
        "Für den Vertragsabschluss muss ein gültiger WBS vorgelegt werden; eine konkrete Stufe ist nicht angegeben.",
        "Die Vermietung ist WBS-gebunden, ohne Angabe einer Einkommensstufe.",
        "Voraussetzung ist ein Wohnberechtigungsschein; zur Prozentstufe enthält das Angebot keine Angabe.",
        "Nur mit gültigem WBS; welche WBS-Stufe gilt, wird nicht genannt.",
        "WBS erforderlich, Förderstufe offen.",
        "Ein Wohnberechtigungsschein ist zwingend, der zulässige Prozentsatz bleibt unbestimmt.",
    ),
    "100": (
        "Zugelassen ist ausschließlich die WBS-Stufe 100 %.",
        "Bewerbung nur mit Wohnberechtigungsschein 100.",
        "Erforderliche Förderstufe: WBS 100.",
        "Die Wohnung ist ausschließlich für einen WBS 100 vorgesehen.",
        "Akzeptiert wird genau WBS 100, keine andere Stufe.",
        "WBS-Bindung: nur 100 %.",
    ),
    "100, 140": (
        "Akzeptiert werden ausschließlich WBS 100 und WBS 140.",
        "Der WBS darf höchstens 140 % betragen.",
        "Berechtigung: WBS 100–140 %, beide Grenzen eingeschlossen.",
        "Zugelassen sind die WBS-Stufen 100 % oder 140 %.",
        "Voraussetzung ist ein WBS bis einschließlich 140 %.",
        "WBS-Obergrenze 140 %; damit gelten 100 % und 140 %.",
    ),
    "160, 180, 220": (
        "WBS-Bereich: 141 % bis 220 %, beide genannten Grenzen eingeschlossen.",
        "Ein WBS 140 berechtigt nicht; zugelassen sind 160 %, 180 % und 220 %.",
        "Für diese Wohnung gilt ein WBS oberhalb von 140 % und höchstens 220 %.",
        "Akzeptiert werden ausschließlich die WBS-Stufen 160, 180 und 220.",
        "Zulassung ab einer Einkommensgrenze von 141 % bis einschließlich WBS 220 %.",
        "WBS größer als 140 %: möglich sind 160 %, 180 % oder 220 %.",
    ),
    "140, 160, 180, 220": (
        "Zulässig ist ein WBS von 140 % bis einschließlich 220 %.",
        "Akzeptiert werden WBS 140, 160, 180 und 220.",
        "Die untere WBS-Grenze von 140 % ist eingeschlossen; die Obergrenze liegt bei 220 %.",
        "Voraussetzung: mindestens WBS 140 und höchstens WBS 220.",
        "WBS-Bereich 140–220 %, einschließlich beider Grenzen.",
        "Ab WBS 140 sind die Stufen 140, 160, 180 und 220 zugelassen.",
    ),
    "100, 140, 160, 180": (
        "Zulässig ist ein WBS bis einschließlich 180 %.",
        "Akzeptiert werden WBS 100, 140, 160 und 180; WBS 220 ist ausgeschlossen.",
        "Die WBS-Obergrenze liegt bei 180 %.",
        "Berechtigung: WBS 100–180 %, einschließlich beider Grenzen.",
        "Zugelassen sind die WBS-Stufen 100, 140, 160 oder 180.",
        "Höchstens WBS 180: möglich sind 100 %, 140 %, 160 % und 180 %.",
    ),
}


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


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
        {
            "raw_text": row["raw_text"],
            "parser_snapshot": row["parser_snapshot"],
        }
    )


def _replace_wbs_phrase(
    case: CleanAIQACase,
    *,
    replacement: str,
) -> CleanAIQACase:
    matching_suffixes = [
        phrase for phrase in WBS_TEXTS if case.raw_text.endswith(phrase)
    ]
    if len(matching_suffixes) != 1:
        raise ValueError("clean case does not end in one canonical WBS phrase")
    base_phrase = matching_suffixes[0]
    raw_text = case.raw_text[: -len(base_phrase)] + replacement
    digest = hashlib.sha256(
        f"{raw_text}\n{case.parser_snapshot.as_dict()}".encode("utf-8")
    ).hexdigest()[:10]
    return replace(
        case,
        case_id=f"clean-v4-{digest}",
        raw_text=raw_text,
        format_variant=f"{case.format_variant}+wbs_semantic_drift",
    )


def generate_wbs_semantic_drift_cases(
    *,
    count: int,
    seed: int,
) -> list[CleanAIQACase]:
    """Generate clean listings with varied, semantically explicit WBS prose."""

    base_cases = generate_clean_ai_qa_cases(
        count=count,
        seed=_derived_seed(seed, "luna-v4-clean-source-cases"),
    )
    rng = random.Random(_derived_seed(seed, "luna-v4-wbs-phrases"))
    offsets = {
        display_wbs: rng.randrange(len(phrases))
        for display_wbs, phrases in WBS_SEMANTIC_DRIFT_PHRASES.items()
    }
    occurrences: Counter[str] = Counter()
    cases: list[CleanAIQACase] = []
    for case in base_cases:
        display_wbs = case.parser_snapshot.display_wbs
        phrases = WBS_SEMANTIC_DRIFT_PHRASES.get(display_wbs)
        if phrases is None:
            raise ValueError(f"missing WBS drift phrases for {display_wbs!r}")
        phrase_index = (offsets[display_wbs] + occurrences[display_wbs]) % len(
            phrases
        )
        occurrences[display_wbs] += 1
        cases.append(
            _replace_wbs_phrase(case, replacement=phrases[phrase_index])
        )
    return cases


def build_luna_v4_cycle_rows() -> dict[
    str,
    tuple[list[dict[str, object]], list[dict[str, object]]],
]:
    datasets: dict[
        str,
        tuple[list[dict[str, object]], list[dict[str, object]]],
    ] = {}
    for split_name, config in LUNA_V4_SPLITS.items():
        seed = int(config["seed"])
        source_cases = generate_wbs_semantic_drift_cases(
            count=sum(LUNA_V4_COUNTS.values()),
            seed=seed,
        )
        datasets[split_name] = build_ai_qa_split_from_clean_cases(
            source_cases=source_cases,
            seed=seed,
            counts=LUNA_V4_COUNTS,
            error_distribution=LUNA_V4_ERROR_DISTRIBUTION,
        )
        input_rows, truth_rows = datasets[split_name]
        verify_ai_qa_split_rows(
            split_name=split_name,
            input_rows=input_rows,
            truth_rows=truth_rows,
            expected_counts=LUNA_V4_COUNTS,
            expected_distribution=LUNA_V4_ERROR_DISTRIBUTION,
        )
        _verify_wbs_drift_inputs(input_rows)
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
        "luna_v3_calibration": (
            DEFAULT_LUNA_V3_DATASET_DIR / "calibration_model_inputs.jsonl"
        ),
        "luna_v3_validation": (
            DEFAULT_LUNA_V3_DATASET_DIR / "validation_model_inputs.jsonl"
        ),
    }


def _verify_wbs_drift_inputs(
    input_rows: Sequence[Mapping[str, object]],
) -> None:
    drift_phrases = {
        phrase
        for phrases in WBS_SEMANTIC_DRIFT_PHRASES.values()
        for phrase in phrases
    }
    for row in input_rows:
        raw_text = str(row["raw_text"])
        if not any(raw_text.endswith(phrase) for phrase in drift_phrases):
            raise ValueError("model input lacks a registered WBS drift phrase")
        if any(raw_text.endswith(phrase) for phrase in WBS_TEXTS):
            raise ValueError("model input retained a base-generator WBS phrase")


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
    calibration = generated["luna_v4_calibration"]
    validation = generated["luna_v4_validation"]
    overlaps = {"calibration_validation": len(calibration & validation)}
    for prior_name, path in _prior_model_input_paths().items():
        prior = {_signature(row) for row in _read_jsonl(path)}
        overlaps[f"calibration_{prior_name}"] = len(calibration & prior)
        overlaps[f"validation_{prior_name}"] = len(validation & prior)
    if any(overlaps.values()):
        raise ValueError(f"Luna-v4 dataset overlap: {overlaps}")
    return overlaps


def write_luna_v4_cycle_datasets(
    output_dir: Path = DEFAULT_LUNA_V4_DATASET_DIR,
) -> dict[str, object]:
    datasets = build_luna_v4_cycle_rows()
    overlaps = _verify_isolation(datasets)
    output_dir.mkdir(parents=True, exist_ok=True)

    split_manifest: dict[str, object] = {}
    for split_name, (input_rows, truth_rows) in datasets.items():
        config = LUNA_V4_SPLITS[split_name]
        input_path = output_dir / str(config["model_inputs"])
        truth_path = output_dir / str(config["truth"])
        _write_jsonl(input_path, input_rows)
        _write_jsonl(truth_path, truth_rows)
        split_manifest[split_name] = {
            "seed": config["seed"],
            "counts": {
                **LUNA_V4_COUNTS,
                "total": sum(LUNA_V4_COUNTS.values()),
            },
            "error_distribution": LUNA_V4_ERROR_DISTRIBUTION,
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
        "schema_version": LUNA_V4_DATASET_SCHEMA_VERSION,
        "experiment": "synthetic offline AI QA Luna-v4 WBS semantic-drift cycle",
        "hypothesis": (
            "Explicit boundary-preserving WBS comparison can close the "
            "141-to-220 failure class without increasing false alerts."
        ),
        "hash_algorithm": "SHA-256",
        "serialization": {
            "encoding": "UTF-8",
            "format": "JSON Lines",
            "json_keys": "sorted",
            "line_ending": "LF",
        },
        "splits": split_manifest,
        "wbs_semantic_drift": {
            "registered_expected_values": sorted(
                WBS_SEMANTIC_DRIFT_PHRASES
            ),
            "phrases_per_expected_value": {
                key: len(value)
                for key, value in sorted(
                    WBS_SEMANTIC_DRIFT_PHRASES.items()
                )
            },
        },
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
    verify_luna_v4_cycle_datasets(output_dir)
    return manifest


def verify_luna_v4_cycle_datasets(
    output_dir: Path = DEFAULT_LUNA_V4_DATASET_DIR,
) -> dict[str, object]:
    manifest_path = output_dir / "dataset_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != LUNA_V4_DATASET_SCHEMA_VERSION:
        raise ValueError("Luna-v4 manifest schema is incorrect")

    datasets: dict[
        str,
        tuple[list[dict[str, object]], list[dict[str, object]]],
    ] = {}
    for split_name, config in LUNA_V4_SPLITS.items():
        split = manifest["splits"][split_name]
        if split.get("seed") != config["seed"]:
            raise ValueError(f"{split_name} seed is incorrect")
        if split.get("counts") != {
            **LUNA_V4_COUNTS,
            "total": sum(LUNA_V4_COUNTS.values()),
        }:
            raise ValueError(f"{split_name} counts are incorrect")
        if split.get("error_distribution") != LUNA_V4_ERROR_DISTRIBUTION:
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
            expected_counts=LUNA_V4_COUNTS,
            expected_distribution=LUNA_V4_ERROR_DISTRIBUTION,
        )
        _verify_wbs_drift_inputs(input_rows)
        datasets[split_name] = (input_rows, truth_rows)

    overlaps = _verify_isolation(datasets)
    if manifest.get("isolation", {}).get("overlaps") != overlaps:
        raise ValueError("Luna-v4 isolation metadata is incorrect")
    return manifest


def public_summary(manifest: Mapping[str, object]) -> dict[str, object]:
    return {
        "hypothesis": manifest["hypothesis"],
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
        description="Generate the Luna-v4 WBS semantic-drift eval cycle.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_LUNA_V4_DATASET_DIR,
    )
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    manifest = (
        verify_luna_v4_cycle_datasets(args.output_dir)
        if args.verify_only
        else write_luna_v4_cycle_datasets(args.output_dir)
    )
    print(json.dumps(public_summary(manifest), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
