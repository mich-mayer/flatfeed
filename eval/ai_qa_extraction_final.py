from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING
from pathlib import Path
from typing import Any

from eval.ai_qa_datasets import (
    LOCKED_HOLDOUT_ERROR_DISTRIBUTION,
    build_ai_qa_custom_split,
    verify_ai_qa_split_rows,
)
from eval.ai_qa_extraction_contract import (
    MODEL_OUTPUT_JSON_SCHEMA,
    SYSTEM_INSTRUCTIONS,
    render_case_input,
)
from eval.ai_qa_extraction_execution import (
    MODEL,
    REASONING_EFFORT,
    SERVICE_TIER,
    STORE,
    TIMEOUT_SECONDS,
    _request_case,
    load_eval_api_key,
    score_predictions,
    verify_model_availability,
)
from eval.ai_qa_extraction_runner import MAX_OUTPUT_TOKENS


SCHEMA_VERSION = "1.0"
FINAL_SEED = 20261001
SPLIT_NAME = "extraction_v1_final_600"

EVAL_ROOT = Path(__file__).resolve().parent
REPO_ROOT = EVAL_ROOT.parent
DATASETS_ROOT = EVAL_ROOT / "datasets"
DATASET_DIR = DATASETS_ROOT / SPLIT_NAME
MODEL_INPUTS_FILE = "model_inputs.jsonl"
TRUTH_FILE = "truth.jsonl"
DATASET_MANIFEST_FILE = "dataset_manifest.json"

FREEZE_PATH = (
    EVAL_ROOT
    / "runs"
    / "extraction-v1-final-600-configuration-freeze.json"
)
OUTPUT_DIR = EVAL_ROOT / "runs" / "extraction-v1-final-600"
PREDICTIONS_FILE = "predictions.jsonl"
REPORT_FILE = "report.json"
RUN_MANIFEST_FILE = "run_manifest.json"

COUNTS = {"clean": 300, "corrupted": 300}
ERROR_DISTRIBUTION = dict(LOCKED_HOLDOUT_ERROR_DISTRIBUTION)

INPUT_PRICE_PER_1M = Decimal("2.00")
CACHED_INPUT_PRICE_PER_1M = Decimal("0.20")
CACHE_WRITE_PRICE_PER_1M = Decimal("2.50")
OUTPUT_PRICE_PER_1M = Decimal("12.00")
PRICING_OBSERVED_DATE = "2026-07-30"
PRICING_SOURCE = "https://developers.openai.com/api/docs/pricing"

FIELD_MINIMUMS = {
    "wbs": 74,
    "rent_kalt": 59,
    "rooms": 49,
    "address_postal_code": 39,
    "district": 30,
    "floor": 25,
    "rent_warm": 20,
}

_MODEL_INPUT_KEYS = {"case_id", "raw_text", "parser_snapshot"}
_TRUTH_KEYS = {
    "case_id",
    "case_type",
    "corrupted_field",
    "expected_value",
    "corrupted_value",
    "corruption_type",
}


class FinalExtractionError(RuntimeError):
    """The frozen extraction-v1 final evaluation cannot proceed safely."""


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


def _sha256_value(value: object) -> str:
    return hashlib.sha256(
        _canonical_json(value).encode("utf-8")
    ).hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(
                f"{path.name}:{line_number} must be a JSON object"
            )
        rows.append(value)
    return rows


def _write_jsonl(
    path: Path,
    rows: Iterable[Mapping[str, object]],
) -> None:
    path.write_text(
        "".join(f"{_canonical_json(row)}\n" for row in rows),
        encoding="utf-8",
    )


def _artifact_entry(path: Path, *, lines: int) -> dict[str, object]:
    return {
        "file": path.name,
        "lines": lines,
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


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
    current = (output_dir / MODEL_INPUTS_FILE).resolve()
    return [
        path
        for path in sorted(DATASETS_ROOT.rglob("*model_inputs.jsonl"))
        if path.resolve() != current
    ]


def _verify_isolation(
    input_rows: Sequence[Mapping[str, object]],
    *,
    output_dir: Path,
) -> dict[str, object]:
    current_signatures = {
        _model_input_signature(row) for row in input_rows
    }
    current_raw_texts = {str(row["raw_text"]) for row in input_rows}
    current_case_ids = {str(row["case_id"]) for row in input_rows}
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
        raise FinalExtractionError(
            "final 600-case data overlaps a prior model-input artifact"
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


def _composition(
    truth_rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    return {
        "case_types": dict(
            sorted(Counter(str(row["case_type"]) for row in truth_rows).items())
        ),
        "corrupted_fields": dict(
            sorted(
                Counter(
                    str(row["corrupted_field"])
                    for row in truth_rows
                    if row["case_type"] == "corrupted"
                ).items()
            )
        ),
        "corruption_types": dict(
            sorted(
                Counter(
                    str(row["corruption_type"])
                    for row in truth_rows
                    if row["case_type"] == "corrupted"
                ).items()
            )
        ),
    }


def build_final_dataset_rows() -> tuple[
    list[dict[str, object]],
    list[dict[str, object]],
]:
    input_rows, truth_rows = build_ai_qa_custom_split(
        seed=FINAL_SEED,
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
    return input_rows, truth_rows


def write_final_dataset(
    output_dir: Path = DATASET_DIR,
) -> dict[str, object]:
    paths = (
        output_dir / MODEL_INPUTS_FILE,
        output_dir / TRUTH_FILE,
        output_dir / DATASET_MANIFEST_FILE,
    )
    if any(path.exists() for path in paths):
        raise FileExistsError("final 600-case dataset already exists")

    input_rows, truth_rows = build_final_dataset_rows()
    isolation = _verify_isolation(input_rows, output_dir=output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    input_path, truth_path, manifest_path = paths
    _write_jsonl(input_path, input_rows)
    _write_jsonl(truth_path, truth_rows)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "experiment": "extraction-v1 final synthetic evaluation",
        "purpose": (
            "One fresh 600-case test after development tuning; not a "
            "production-accuracy estimate."
        ),
        "seed": FINAL_SEED,
        "split": SPLIT_NAME,
        "locked": True,
        "permitted_use": "one frozen final evaluation only",
        "counts": {**COUNTS, "total": sum(COUNTS.values())},
        "error_distribution": ERROR_DISTRIBUTION,
        "composition": _composition(truth_rows),
        "model_inputs": _artifact_entry(
            input_path,
            lines=len(input_rows),
        ),
        "truth": _artifact_entry(truth_path, lines=len(truth_rows)),
        "isolation": isolation,
        "boundaries": {
            "new_cases": True,
            "prior_cases_reused": False,
            "hidden_truth_separate_from_model_inputs": True,
            "openai_called_during_generation": False,
            "product_runtime_modified": False,
            "production_accuracy_claim": False,
        },
    }
    manifest_path.write_text(
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    verify_final_dataset(output_dir)
    return manifest


def verify_final_dataset(
    output_dir: Path = DATASET_DIR,
) -> dict[str, Any]:
    manifest_path = output_dir / DATASET_MANIFEST_FILE
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    input_path = output_dir / str(manifest["model_inputs"]["file"])
    truth_path = output_dir / str(manifest["truth"]["file"])
    if _sha256_file(input_path) != manifest["model_inputs"]["sha256"]:
        raise FinalExtractionError("final model-input hash mismatch")
    if _sha256_file(truth_path) != manifest["truth"]["sha256"]:
        raise FinalExtractionError("final truth hash mismatch")

    input_rows = _read_jsonl(input_path)
    truth_rows = _read_jsonl(truth_path)
    verify_ai_qa_split_rows(
        split_name=SPLIT_NAME,
        input_rows=input_rows,
        truth_rows=truth_rows,
        expected_counts=COUNTS,
        expected_distribution=ERROR_DISTRIBUTION,
    )
    expected_inputs, expected_truth = build_final_dataset_rows()
    if input_rows != expected_inputs or truth_rows != expected_truth:
        raise FinalExtractionError(
            "final dataset is not reproducible from its frozen seed"
        )
    if manifest["composition"] != _composition(truth_rows):
        raise FinalExtractionError("final dataset composition mismatch")
    isolation = _verify_isolation(input_rows, output_dir=output_dir)
    if manifest["isolation"] != isolation:
        raise FinalExtractionError("final dataset isolation mismatch")
    return manifest


def calculate_cost_usd(usage: Mapping[str, int]) -> Decimal:
    regular = Decimal(
        usage["input_tokens"]
        - usage["cached_input_tokens"]
        - usage["cache_write_tokens"]
    )
    return (
        regular * INPUT_PRICE_PER_1M
        + Decimal(usage["cached_input_tokens"])
        * CACHED_INPUT_PRICE_PER_1M
        + Decimal(usage["cache_write_tokens"])
        * CACHE_WRITE_PRICE_PER_1M
        + Decimal(usage["output_tokens"]) * OUTPUT_PRICE_PER_1M
    ) / Decimal(1_000_000)


def _round_up_cents(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_CEILING)


def _development_cost_projection() -> Decimal:
    path = (
        EVAL_ROOT
        / "runs"
        / "extraction-v1-development"
        / PREDICTIONS_FILE
    )
    total = Decimal("0")
    for row in _read_jsonl(path):
        usage = row.get("usage")
        if isinstance(usage, dict):
            total += calculate_cost_usd(usage)
    return total * Decimal(5)


def build_configuration_freeze() -> dict[str, object]:
    manifest = verify_final_dataset()
    input_path = DATASET_DIR / MODEL_INPUTS_FILE
    truth_path = DATASET_DIR / TRUTH_FILE
    input_rows = _read_jsonl(input_path)
    rendered = [render_case_input(row) for row in input_rows]
    input_upper = len(input_rows) * len(
        SYSTEM_INSTRUCTIONS.encode("utf-8")
    ) + sum(len(value.encode("utf-8")) for value in rendered)
    output_upper = len(input_rows) * MAX_OUTPUT_TOKENS
    worst_case = (
        Decimal(input_upper) * CACHE_WRITE_PRICE_PER_1M
        + Decimal(output_upper) * OUTPUT_PRICE_PER_1M
    ) / Decimal(1_000_000)
    source_files = {
        "contract": EVAL_ROOT / "ai_qa_extraction_contract.py",
        "comparator": EVAL_ROOT / "ai_qa_extraction_compare.py",
        "scorer_and_execution": (
            EVAL_ROOT / "ai_qa_extraction_execution.py"
        ),
        "final_runner": Path(__file__),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "final_600_authorized_once",
        "created_on": PRICING_OBSERVED_DATE,
        "dataset": {
            "split": SPLIT_NAME,
            "case_count": len(input_rows),
            "clean": COUNTS["clean"],
            "corrupted": COUNTS["corrupted"],
            "error_distribution": ERROR_DISTRIBUTION,
            "manifest_sha256": _sha256_file(
                DATASET_DIR / DATASET_MANIFEST_FILE
            ),
            "model_inputs_sha256": _sha256_file(input_path),
            "truth_sha256": _sha256_file(truth_path),
            "prior_artifact_count": manifest["isolation"][
                "prior_artifact_count"
            ],
            "zero_overlap_with_prior_inputs": True,
        },
        "configuration": {
            "model": MODEL,
            "reasoning_effort": REASONING_EFFORT,
            "prompt_version": "extraction-v1",
            "max_output_tokens": MAX_OUTPUT_TOKENS,
            "retries": 0,
            "service_tier": SERVICE_TIER,
            "timeout_seconds": TIMEOUT_SECONDS,
            "store": STORE,
            "strict_structured_outputs": True,
            "model_receives_parser_snapshot": False,
        },
        "hashes": {
            "prompt_sha256": hashlib.sha256(
                SYSTEM_INSTRUCTIONS.encode("utf-8")
            ).hexdigest(),
            "output_schema_sha256": _sha256_value(
                MODEL_OUTPUT_JSON_SCHEMA
            ),
            **{
                f"{name}_sha256": _sha256_file(path)
                for name, path in source_files.items()
            },
        },
        "release_gates": {
            "successful_checks": "at least 597/600",
            "errors_detected": "at least 294/300",
            "correct_fields": "at least 294/300",
            "clean_false_alerts": "at most 3/300",
            "field_minimums": FIELD_MINIMUMS,
            "all_gates_must_pass": True,
        },
        "requests": {
            "case_requests": len(input_rows),
            "model_availability_checks": 1,
            "retries": 0,
            "maximum_total_api_calls": len(input_rows) + 1,
        },
        "pricing": {
            "input_per_1m_usd": str(INPUT_PRICE_PER_1M),
            "cached_input_per_1m_usd": str(
                CACHED_INPUT_PRICE_PER_1M
            ),
            "cache_write_per_1m_usd": str(
                CACHE_WRITE_PRICE_PER_1M
            ),
            "output_per_1m_usd": str(OUTPUT_PRICE_PER_1M),
            "observed_date": PRICING_OBSERVED_DATE,
            "source": PRICING_SOURCE,
            "verified_against_official_docs": True,
        },
        "budget": {
            "expected_from_repriced_development_usage_usd": str(
                _development_cost_projection().quantize(
                    Decimal("0.000001")
                )
            ),
            "input_token_upper_bound": input_upper,
            "output_token_upper_bound": output_upper,
            "worst_case_cost_usd": str(
                worst_case.quantize(Decimal("0.000001"))
            ),
            "hard_limit_usd": str(_round_up_cents(worst_case)),
            "method": (
                "Expected cost scales the recorded 120-case token usage by "
                "five at current prices. The hard limit prices UTF-8 bytes "
                "as input tokens, reserves maximum output for every case, "
                "and prices all input at the higher cache-write rate."
            ),
        },
        "authorization": {
            "final_runs": 1,
            "case_requests": len(input_rows),
            "retries": 0,
            "resume_or_overwrite": False,
            "post_run_tuning_or_rescore": False,
        },
        "boundaries": {
            "synthetic_challenge_set": True,
            "production_accuracy": False,
            "natural_error_prevalence": False,
            "product_runtime_modified": False,
        },
    }


def verify_configuration_freeze(
    path: Path = FREEZE_PATH,
) -> dict[str, Any]:
    stored = json.loads(path.read_text(encoding="utf-8"))
    expected = build_configuration_freeze()
    if stored != expected:
        raise FinalExtractionError(
            "final configuration freeze differs from code or data"
        )
    return stored


def _wilson_95(successes: int, total: int) -> dict[str, float]:
    if total <= 0:
        raise ValueError("Wilson interval requires a positive total")
    z = 1.959963984540054
    proportion = successes / total
    denominator = 1 + z * z / total
    center = (proportion + z * z / (2 * total)) / denominator
    margin = (
        z
        * math.sqrt(
            proportion * (1 - proportion) / total
            + z * z / (4 * total * total)
        )
        / denominator
    )
    return {
        "lower": max(0.0, center - margin),
        "upper": min(1.0, center + margin),
    }


def _percentile(values: Sequence[float], percentile: float) -> float:
    if not values:
        raise ValueError("percentile requires at least one value")
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def build_final_gate(report: Mapping[str, Any]) -> dict[str, object]:
    metrics = report["metrics"]
    fields = report["per_field"]
    gates = {
        "successful_checks_at_least_597_of_600": (
            metrics["successful_check_rate"]["numerator"] >= 597
        ),
        "errors_detected_at_least_294_of_300": (
            metrics["parser_error_detection_rate"]["numerator"] >= 294
        ),
        "correct_fields_at_least_294_of_300": (
            metrics["correct_field_detection_rate"]["numerator"] >= 294
        ),
        "clean_false_alerts_at_most_3_of_300": (
            metrics["false_alert_rate"]["numerator"] <= 3
        ),
        **{
            f"{field}_at_least_{minimum}_of_"
            f"{ERROR_DISTRIBUTION[field]}": (
                fields[field]["correct_field"] >= minimum
            )
            for field, minimum in FIELD_MINIMUMS.items()
        },
    }
    passed = all(gates.values())
    return {
        "status": "pass" if passed else "fail",
        "all_gates_passed": passed,
        "gates": gates,
        "final_synthetic_result_accepted": passed,
        "product_runtime_integration_authorized": False,
    }


def score_final_predictions(
    *,
    input_rows: Sequence[Mapping[str, Any]],
    truth_rows: Sequence[Mapping[str, Any]],
    prediction_rows: Sequence[Mapping[str, Any]],
) -> dict[str, object]:
    report = score_predictions(
        input_rows=input_rows,
        truth_rows=truth_rows,
        prediction_rows=prediction_rows,
    )
    metrics = report["metrics"]
    for metric in (
        "successful_check_rate",
        "parser_error_detection_rate",
        "false_alert_rate",
        "correct_field_detection_rate",
        "case_accuracy",
    ):
        value = metrics[metric]
        value["wilson_95"] = _wilson_95(
            int(value["numerator"]),
            int(value["denominator"]),
        )
    detected = int(
        metrics["parser_error_detection_rate"]["numerator"]
    )
    false_alerts = int(metrics["false_alert_rate"]["numerator"])
    precision_total = detected + false_alerts
    metrics["challenge_set_precision"] = {
        "numerator": detected,
        "denominator": precision_total,
        "value": (
            detected / precision_total if precision_total else None
        ),
        "wilson_95": (
            _wilson_95(detected, precision_total)
            if precision_total
            else None
        ),
        "production_precision": False,
    }

    latencies = [
        float(row["latency_ms"])
        for row in prediction_rows
        if isinstance(row.get("latency_ms"), (int, float))
    ]
    usage_totals = Counter()
    total_cost = Decimal("0")
    for row in prediction_rows:
        usage = row.get("usage")
        if isinstance(usage, dict):
            usage_totals.update(
                {
                    key: int(value)
                    for key, value in usage.items()
                }
            )
        if row.get("cost_usd") is not None:
            total_cost += Decimal(str(row["cost_usd"]))
    report["operations"] = {
        "latency_ms": {
            "p50": statistics.median(latencies),
            "p95": _percentile(latencies, 0.95),
        },
        "usage": dict(sorted(usage_totals.items())),
        "recorded_cost_usd": float(total_cost),
        "cost_per_listing_usd": float(
            total_cost / Decimal(len(prediction_rows))
        ),
    }
    report["gate_decision"] = build_final_gate(report)
    report["evidence_boundary"] = (
        "Balanced synthetic challenge-set evidence; not production "
        "precision, natural parser-error prevalence, or real-source accuracy."
    )
    return report


def _write_jsonl_row(path: Path, row: Mapping[str, object]) -> None:
    with path.open("a", encoding="utf-8") as artifact:
        artifact.write(_canonical_json(row) + "\n")
        artifact.flush()


def execute_frozen_final() -> dict[str, object]:
    freeze = verify_configuration_freeze()
    if OUTPUT_DIR.exists():
        raise FileExistsError(
            "final run artifacts already exist; refusing overwrite"
        )
    input_rows = _read_jsonl(DATASET_DIR / MODEL_INPUTS_FILE)
    api_key = load_eval_api_key()
    from eval.ai_qa_extraction_execution import _new_openai_client

    client = _new_openai_client(api_key)
    verify_model_availability(client)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=False)
    predictions_path = OUTPUT_DIR / PREDICTIONS_FILE
    report_path = OUTPUT_DIR / REPORT_FILE
    manifest_path = OUTPUT_DIR / RUN_MANIFEST_FILE
    manifest: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "status": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "configuration_freeze_sha256": _sha256_file(FREEZE_PATH),
        "dataset": freeze["dataset"],
        "configuration": freeze["configuration"],
        "release_gates": freeze["release_gates"],
        "budget": freeze["budget"],
        "credential": {
            "source": ".env.eval.local",
            "variable": "OPENAI_API_KEY",
            "value_persisted": False,
        },
    }
    manifest_path.write_text(
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    completed = 0
    invalid_outputs = 0
    technical_failures = 0
    actual_cost = Decimal("0")
    hard_limit = Decimal(str(freeze["budget"]["hard_limit_usd"]))
    for case in input_rows:
        prediction = _request_case(client=client, case=case)
        usage = prediction.get("usage")
        if isinstance(usage, dict):
            current_cost = calculate_cost_usd(usage)
            prediction["cost_usd"] = float(current_cost)
            actual_cost += current_cost
        if actual_cost > hard_limit:
            raise FinalExtractionError(
                "final run exceeded its frozen hard budget"
            )
        if prediction["status"] == "completed":
            completed += 1
        elif prediction["status"] == "invalid_output":
            invalid_outputs += 1
        else:
            technical_failures += 1
        _write_jsonl_row(predictions_path, prediction)

    truth_rows = _read_jsonl(DATASET_DIR / TRUTH_FILE)
    predictions = _read_jsonl(predictions_path)
    report = score_final_predictions(
        input_rows=input_rows,
        truth_rows=truth_rows,
        prediction_rows=predictions,
    )
    report_path.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    manifest["status"] = "completed"
    manifest["completed_at"] = datetime.now(timezone.utc).isoformat()
    manifest["result"] = {
        "completed_cases": completed,
        "invalid_outputs": invalid_outputs,
        "technical_failures": technical_failures,
        "recorded_cost_usd": float(actual_cost),
        "predictions_sha256": _sha256_file(predictions_path),
        "report_sha256": _sha256_file(report_path),
        "gate_status": report["gate_decision"]["status"],
        "final_synthetic_result_accepted": report[
            "gate_decision"
        ]["final_synthetic_result_accepted"],
    }
    manifest_path.write_text(
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "report": report,
        "recorded_cost_usd": float(actual_cost),
        "artifacts": {
            "predictions": str(
                predictions_path.relative_to(REPO_ROOT)
            ),
            "report": str(report_path.relative_to(REPO_ROOT)),
            "run_manifest": str(manifest_path.relative_to(REPO_ROOT)),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate, freeze, verify, or execute the extraction-v1 "
            "final 600-case synthetic evaluation."
        )
    )
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--generate", action="store_true")
    actions.add_argument("--print-freeze", action="store_true")
    actions.add_argument("--verify-freeze", action="store_true")
    actions.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    if args.generate:
        result: object = write_final_dataset()
    elif args.print_freeze:
        result = build_configuration_freeze()
    elif args.verify_freeze:
        result = verify_configuration_freeze()
    else:
        result = execute_frozen_final()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
