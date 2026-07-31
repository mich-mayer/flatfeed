from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol

import openai
from dotenv import dotenv_values
from openai import OpenAI

from eval.ai_qa_extraction_compare import compare_extraction_to_snapshot
from eval.ai_qa_extraction_contract import (
    ExtractionOutputError,
    RESPONSES_TEXT_FORMAT,
    SYSTEM_INSTRUCTIONS,
    parse_extraction_output,
    render_case_input,
)
from eval.ai_qa_extraction_runner import (
    CACHED_INPUT_PRICE_PER_1M,
    CACHE_WRITE_PRICE_PER_1M,
    DEFAULT_PLAN_PATH,
    INPUT_PRICE_PER_1M,
    MAX_OUTPUT_TOKENS,
    MODEL,
    OUTPUT_PRICE_PER_1M,
    PRICING_OBSERVED_DATE,
    PRICING_SOURCE,
    REASONING_EFFORT,
    SERVICE_TIER,
    STORE,
    TIMEOUT_SECONDS,
    _canonical_json,
    _read_jsonl,
    _sha256_file,
    verify_dry_run_plan,
)
from eval.ai_qa_review_development import (
    DEFAULT_OUTPUT_DIR as DEFAULT_DATASET_DIR,
)
from eval.ai_qa_review_development import MODEL_INPUTS_FILE, TRUTH_FILE
from eval.ai_qa_scorer import (
    ERROR_FIELDS,
    ERROR_FIELD_LABELS,
    TRUTH_FIELD_TO_ERROR_FIELD,
)


EXECUTION_VERSION = "extraction-execution-v1"
SCORER_VERSION = "extraction-v1"
FREEZE_PATH = (
    Path(__file__).with_name("runs")
    / "extraction-v1-development-configuration-freeze.json"
)
OUTPUT_DIR = (
    Path(__file__).with_name("runs")
    / "extraction-v1-development"
)
PREDICTIONS_FILE = "predictions.jsonl"
REPORT_FILE = "report.json"
RUN_MANIFEST_FILE = "run_manifest.json"
RESCORED_REPORT_FILE = "report-rescored.json"
RESCORE_MANIFEST_FILE = "rescore_manifest.json"

REPO_ROOT = Path(__file__).resolve().parents[1]
EVAL_ROOT = Path(__file__).resolve().parent
EVAL_ENV_PATH = REPO_ROOT / ".env.eval.local"

_MODEL_INPUT_KEYS = {"case_id", "raw_text", "parser_snapshot"}
_TRUTH_KEYS = {
    "case_id",
    "case_type",
    "corrupted_field",
    "expected_value",
    "corrupted_value",
    "corruption_type",
}


class ExtractionExecutionError(RuntimeError):
    """The frozen extraction-v1 development run cannot proceed safely."""


class ResponsesClient(Protocol):
    models: object
    responses: object


def build_configuration_freeze() -> dict[str, object]:
    plan = verify_dry_run_plan()
    return {
        "schema_version": "1.0",
        "status": "development_authorized_once",
        "created_on": PRICING_OBSERVED_DATE,
        "execution_version": EXECUTION_VERSION,
        "dry_run_plan_sha256": _sha256_file(DEFAULT_PLAN_PATH),
        "dataset": plan["dataset"],
        "configuration": plan["configuration"],
        "hashes": plan["hashes"],
        "requests": plan["requests"],
        "preflight": plan["preflight"],
        "pricing": {
            **plan["pricing"],
            "must_refresh_before_execute": False,
            "verified_against_official_docs": True,
        },
        "development_targets": plan["development_targets"],
        "authorization": {
            "development_runs": 1,
            "case_requests": 120,
            "retries": 0,
            "resume_or_overwrite": False,
            "final_600_case_run": False,
        },
        "boundaries": plan["boundaries"],
    }


def verify_configuration_freeze(
    path: Path = FREEZE_PATH,
) -> dict[str, object]:
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExtractionExecutionError(
            "valid extraction-v1 configuration freeze is required"
        ) from exc
    expected = build_configuration_freeze()
    if stored != expected:
        raise ExtractionExecutionError(
            "configuration freeze differs from current code or dataset"
        )
    return stored


def load_eval_api_key() -> str:
    values = dotenv_values(EVAL_ENV_PATH)
    api_key = values.get("OPENAI_API_KEY")
    if not isinstance(api_key, str) or not api_key.strip():
        raise ExtractionExecutionError(
            "OPENAI_API_KEY is missing from .env.eval.local"
        )
    return api_key.strip()


def _new_openai_client(api_key: str) -> ResponsesClient:
    return OpenAI(api_key=api_key, base_url="https://api.openai.com/v1")


def _classify_api_exception(exc: Exception) -> str:
    if isinstance(exc, openai.APITimeoutError):
        return "api_timeout"
    if isinstance(exc, openai.APIConnectionError):
        return "api_connection"
    if isinstance(exc, openai.RateLimitError):
        return "api_rate_limit"
    if isinstance(exc, openai.InternalServerError):
        return "api_server"
    if isinstance(exc, openai.AuthenticationError):
        return "api_authentication"
    if isinstance(exc, openai.NotFoundError):
        return "model_unavailable"
    if isinstance(exc, openai.BadRequestError):
        return "api_bad_request"
    if isinstance(exc, openai.APIStatusError):
        return "api_status"
    return "unknown_api_error"


def verify_model_availability(client: ResponsesClient) -> None:
    try:
        record = client.models.retrieve(MODEL)
    except Exception as exc:
        raise ExtractionExecutionError(
            "model availability check failed: "
            f"{_classify_api_exception(exc)}"
        ) from None
    if getattr(record, "id", None) != MODEL:
        raise ExtractionExecutionError(
            "model availability check returned a different model ID"
        )


def _usage_from_response(response: object) -> dict[str, int] | None:
    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    input_details = getattr(usage, "input_tokens_details", None)
    output_details = getattr(usage, "output_tokens_details", None)
    values = {
        "input_tokens": int(getattr(usage, "input_tokens", 0)),
        "cached_input_tokens": int(
            getattr(input_details, "cached_tokens", 0) or 0
        ),
        "cache_write_tokens": int(
            getattr(input_details, "cache_write_tokens", 0) or 0
        ),
        "output_tokens": int(getattr(usage, "output_tokens", 0)),
        "reasoning_tokens": int(
            getattr(output_details, "reasoning_tokens", 0) or 0
        ),
    }
    if any(value < 0 for value in values.values()):
        raise ExtractionExecutionError(
            "response usage contains negative values"
        )
    if (
        values["cached_input_tokens"] + values["cache_write_tokens"]
        > values["input_tokens"]
        or values["reasoning_tokens"] > values["output_tokens"]
    ):
        raise ExtractionExecutionError(
            "response usage details exceed their totals"
        )
    return values


def calculate_cost_usd(usage: Mapping[str, int]) -> Decimal:
    uncached = Decimal(
        usage["input_tokens"]
        - usage["cached_input_tokens"]
        - usage["cache_write_tokens"]
    )
    cached = Decimal(usage["cached_input_tokens"])
    cache_write = Decimal(usage["cache_write_tokens"])
    output = Decimal(usage["output_tokens"])
    return (
        uncached * INPUT_PRICE_PER_1M
        + cached * CACHED_INPUT_PRICE_PER_1M
        + cache_write * CACHE_WRITE_PRICE_PER_1M
        + output * OUTPUT_PRICE_PER_1M
    ) / Decimal(1_000_000)


def _response_has_refusal(response: object) -> bool:
    for output_item in getattr(response, "output", []) or []:
        for content_item in getattr(output_item, "content", []) or []:
            if getattr(content_item, "type", None) == "refusal":
                return True
    return False


def _request_case(
    *,
    client: ResponsesClient,
    case: Mapping[str, object],
    monotonic_fn: Callable[[], float] = time.monotonic,
) -> dict[str, object]:
    started = monotonic_fn()
    try:
        response = client.responses.create(
            model=MODEL,
            reasoning={"effort": REASONING_EFFORT},
            instructions=SYSTEM_INSTRUCTIONS,
            input=render_case_input(case),
            text={"format": RESPONSES_TEXT_FORMAT},
            max_output_tokens=MAX_OUTPUT_TOKENS,
            service_tier=SERVICE_TIER,
            store=STORE,
            timeout=TIMEOUT_SECONDS,
        )
    except Exception as exc:
        return {
            "case_id": str(case["case_id"]),
            "status": "technical_failure",
            "failure": {"type": _classify_api_exception(exc)},
            "latency_ms": (monotonic_fn() - started) * 1000,
            "retry_count": 0,
        }

    latency_ms = (monotonic_fn() - started) * 1000
    failure_type: str | None = None
    if getattr(response, "status", None) != "completed":
        failure_type = "response_incomplete"
    elif getattr(response, "model", None) != MODEL:
        failure_type = "response_model_mismatch"
    elif _response_has_refusal(response):
        failure_type = "response_refusal"
    raw_output = getattr(response, "output_text", None)
    if failure_type is None and (
        not isinstance(raw_output, str) or not raw_output
    ):
        failure_type = "response_missing_output"

    row: dict[str, object] = {
        "case_id": str(case["case_id"]),
        "latency_ms": latency_ms,
        "retry_count": 0,
    }
    usage = _usage_from_response(response)
    if usage is not None:
        row["usage"] = usage
        row["cost_usd"] = float(calculate_cost_usd(usage))
    if failure_type is not None:
        row["status"] = "technical_failure"
        row["failure"] = {"type": failure_type}
        return row

    row["raw_output"] = raw_output
    try:
        extraction = parse_extraction_output(
            raw_output,
            raw_text=str(case["raw_text"]),
        )
        review = compare_extraction_to_snapshot(
            extraction=extraction,
            parser_snapshot=case["parser_snapshot"],
        )
    except (ExtractionOutputError, ValueError) as exc:
        row["status"] = "invalid_output"
        row["failure"] = {"type": str(exc)}
        return row

    row["status"] = "completed"
    row["decision"] = {
        "review_required": review.review_required,
        "issues": [asdict(issue) for issue in review.issues],
    }
    return row


def _index_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    required_keys: set[str],
    label: str,
) -> dict[str, Mapping[str, Any]]:
    indexed: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if set(row) != required_keys:
            raise ValueError(f"{label} row does not match its schema")
        case_id = row.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError(f"{label} case_id must be a non-empty string")
        if case_id in indexed:
            raise ValueError(f"duplicate {label} case_id: {case_id}")
        indexed[case_id] = row
    return indexed


def _index_predictions(
    rows: Sequence[Mapping[str, Any]],
    *,
    expected_ids: set[str],
) -> dict[str, Mapping[str, Any]]:
    indexed: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        case_id = row.get("case_id")
        if not isinstance(case_id, str) or case_id not in expected_ids:
            raise ValueError("prediction has an invalid case_id")
        if case_id in indexed:
            raise ValueError(f"duplicate prediction case_id: {case_id}")
        if row.get("status") not in {
            "completed",
            "invalid_output",
            "technical_failure",
        }:
            raise ValueError(f"invalid prediction status for {case_id}")
        indexed[case_id] = row
    missing = expected_ids - set(indexed)
    if missing:
        raise ValueError(
            f"prediction artifact is incomplete; missing {len(missing)} cases"
        )
    return indexed


def _ratio(numerator: int, denominator: int) -> dict[str, object]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "value": numerator / denominator if denominator else None,
    }


def score_predictions(
    *,
    input_rows: Sequence[Mapping[str, Any]],
    truth_rows: Sequence[Mapping[str, Any]],
    prediction_rows: Sequence[Mapping[str, Any]],
) -> dict[str, object]:
    inputs = _index_rows(
        input_rows,
        required_keys=_MODEL_INPUT_KEYS,
        label="model input",
    )
    truth = _index_rows(
        truth_rows,
        required_keys=_TRUTH_KEYS,
        label="truth",
    )
    if set(inputs) != set(truth):
        raise ValueError("model inputs and truth contain different case IDs")
    predictions = _index_predictions(
        prediction_rows,
        expected_ids=set(truth),
    )

    clean_total = 0
    corrupted_total = 0
    successful = 0
    detected = 0
    correct_field = 0
    false_alerts = 0
    correct_cases = 0
    review_reasons: Counter[str] = Counter()
    failure_types: Counter[str] = Counter()
    per_field = {field: Counter() for field in ERROR_FIELDS}
    false_negatives: list[dict[str, object]] = []
    false_positives: list[dict[str, object]] = []
    wrong_fields: list[dict[str, object]] = []

    for case_id, truth_row in truth.items():
        prediction = predictions[case_id]
        completed = prediction["status"] == "completed"
        if completed:
            successful += 1
            decision = prediction.get("decision")
            if not isinstance(decision, dict):
                raise ValueError("completed prediction lacks decision")
            issues = decision.get("issues")
            if not isinstance(issues, list):
                raise ValueError("completed prediction issues must be a list")
            issue_fields = [
                str(issue["error_field"])
                for issue in issues
                if isinstance(issue, dict) and issue.get("error_field")
            ]
            for issue in issues:
                if isinstance(issue, dict) and issue.get("review_reason"):
                    review_reasons[str(issue["review_reason"])] += 1
            review_required = bool(decision.get("review_required"))
        else:
            failure = prediction.get("failure")
            failure_type = (
                str(failure.get("type"))
                if isinstance(failure, dict) and failure.get("type")
                else str(prediction["status"])
            )
            failure_types[failure_type] += 1
            issue_fields = []
            review_required = False

        if truth_row["case_type"] == "clean":
            clean_total += 1
            if review_required:
                false_alerts += 1
                false_positives.append(
                    {
                        "case_id": case_id,
                        "issue_fields": issue_fields,
                    }
                )
            elif completed:
                correct_cases += 1
            continue

        corrupted_total += 1
        expected_field = TRUTH_FIELD_TO_ERROR_FIELD[
            str(truth_row["corrupted_field"])
        ]
        field_counts = per_field[expected_field]
        field_counts["total"] += 1
        if review_required:
            detected += 1
            field_counts["detected"] += 1
            if issue_fields == [expected_field]:
                correct_field += 1
                correct_cases += 1
                field_counts["correct_field"] += 1
            else:
                wrong_fields.append(
                    {
                        "case_id": case_id,
                        "expected_field": expected_field,
                        "issue_fields": issue_fields,
                    }
                )
        else:
            false_negatives.append(
                {
                    "case_id": case_id,
                    "expected_field": expected_field,
                    "status": prediction["status"],
                }
            )

    field_report = {
        field: {
            "label": ERROR_FIELD_LABELS[field],
            "total": per_field[field]["total"],
            "detected": per_field[field]["detected"],
            "correct_field": per_field[field]["correct_field"],
            "correct_field_rate": _ratio(
                per_field[field]["correct_field"],
                per_field[field]["total"],
            ),
        }
        for field in ERROR_FIELDS
    }
    metrics = {
        "successful_check_rate": _ratio(successful, len(truth)),
        "parser_error_detection_rate": _ratio(
            detected,
            corrupted_total,
        ),
        "false_alert_rate": _ratio(false_alerts, clean_total),
        "correct_field_detection_rate": _ratio(
            correct_field,
            corrupted_total,
        ),
        "case_accuracy": _ratio(correct_cases, len(truth)),
    }
    report: dict[str, object] = {
        "scorer_version": SCORER_VERSION,
        "counts": {
            "attempted": len(truth),
            "clean": clean_total,
            "corrupted": corrupted_total,
        },
        "metrics": metrics,
        "per_field": field_report,
        "review_reasons": dict(sorted(review_reasons.items())),
        "failure_types": dict(sorted(failure_types.items())),
        "diagnostics": {
            "false_negatives": false_negatives,
            "false_positives": false_positives,
            "wrong_fields": wrong_fields,
        },
    }
    report["gate_decision"] = build_gate_decision(report)
    return report


def rebuild_saved_decisions(
    *,
    input_rows: Sequence[Mapping[str, Any]],
    prediction_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, object]]:
    inputs = _index_rows(
        input_rows,
        required_keys=_MODEL_INPUT_KEYS,
        label="model input",
    )
    rebuilt: list[dict[str, object]] = []
    for prediction in prediction_rows:
        row = dict(prediction)
        if row.get("status") != "completed":
            rebuilt.append(row)
            continue
        case_id = row.get("case_id")
        if not isinstance(case_id, str) or case_id not in inputs:
            raise ValueError("saved prediction has an invalid case_id")
        raw_output = row.get("raw_output")
        if not isinstance(raw_output, str) or not raw_output:
            raise ValueError("completed saved prediction lacks raw_output")
        case = inputs[case_id]
        extraction = parse_extraction_output(
            raw_output,
            raw_text=str(case["raw_text"]),
        )
        review = compare_extraction_to_snapshot(
            extraction=extraction,
            parser_snapshot=case["parser_snapshot"],
        )
        row["decision"] = {
            "review_required": review.review_required,
            "issues": [asdict(issue) for issue in review.issues],
        }
        rebuilt.append(row)
    return rebuilt


def _metric_numerator(
    report: Mapping[str, object],
    name: str,
) -> int:
    return int(report["metrics"][name]["numerator"])


def build_gate_decision(
    report: Mapping[str, object],
) -> dict[str, object]:
    fields = report["per_field"]
    false_alerts = _metric_numerator(report, "false_alert_rate")
    gates = {
        "successful_checks_at_least_119_of_120": (
            _metric_numerator(report, "successful_check_rate") >= 119
        ),
        "errors_detected_at_least_68_of_70": (
            _metric_numerator(report, "parser_error_detection_rate") >= 68
        ),
        "correct_fields_at_least_68_of_70": (
            _metric_numerator(report, "correct_field_detection_rate") >= 68
        ),
        "clean_false_alerts_at_most_1_of_50": false_alerts <= 1,
        "no_false_alert_regression_from_previous_0_of_50": (
            false_alerts == 0
        ),
        "rooms_at_least_19_of_20": (
            fields["rooms"]["correct_field"] >= 19
        ),
        "wbs_10_of_10": fields["wbs"]["correct_field"] == 10,
        "rent_kalt_10_of_10": (
            fields["rent_kalt"]["correct_field"] == 10
        ),
        "address_postal_code_10_of_10": (
            fields["address_postal_code"]["correct_field"] == 10
        ),
        "district_8_of_8": fields["district"]["correct_field"] == 8,
        "floor_6_of_6": fields["floor"]["correct_field"] == 6,
        "rent_warm_6_of_6": (
            fields["rent_warm"]["correct_field"] == 6
        ),
        "improves_previous_66_of_70_correct_fields": (
            _metric_numerator(
                report,
                "correct_field_detection_rate",
            )
            > 66
        ),
        "improves_previous_17_of_20_rooms": (
            fields["rooms"]["correct_field"] > 17
        ),
    }
    passed = all(gates.values())
    return {
        "status": "pass" if passed else "fail",
        "all_gates_passed": passed,
        "gates": gates,
        "new_600_case_evaluation_authorized": passed,
    }


def _assert_artifacts_absent() -> None:
    if OUTPUT_DIR.exists():
        raise FileExistsError(
            "extraction-v1 run artifacts already exist; refusing overwrite"
        )


def _write_jsonl_row(path: Path, row: Mapping[str, object]) -> None:
    with path.open("a", encoding="utf-8") as artifact:
        artifact.write(_canonical_json(row) + "\n")
        artifact.flush()


def execute_frozen_run(
    *,
    api_key_loader: Callable[[], str] = load_eval_api_key,
    client_factory: Callable[[str], ResponsesClient] = _new_openai_client,
    monotonic_fn: Callable[[], float] = time.monotonic,
) -> dict[str, object]:
    freeze = verify_configuration_freeze()
    _assert_artifacts_absent()
    cases = _read_jsonl(DEFAULT_DATASET_DIR / MODEL_INPUTS_FILE)
    truth_rows = _read_jsonl(DEFAULT_DATASET_DIR / TRUTH_FILE)

    api_key = api_key_loader()
    client = client_factory(api_key)
    verify_model_availability(client)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=False)
    predictions_path = OUTPUT_DIR / PREDICTIONS_FILE
    report_path = OUTPUT_DIR / REPORT_FILE
    manifest_path = OUTPUT_DIR / RUN_MANIFEST_FILE
    manifest: dict[str, object] = {
        "schema_version": "1.0",
        "execution_version": EXECUTION_VERSION,
        "status": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "configuration_freeze_sha256": _sha256_file(FREEZE_PATH),
        "dataset": freeze["dataset"],
        "configuration": freeze["configuration"],
        "budget": {
            "hard_limit_usd": freeze["preflight"][
                "hard_budget_limit_usd"
            ],
            "pricing": freeze["pricing"],
        },
        "credential": {
            "source": ".env.eval.local",
            "variable": "OPENAI_API_KEY",
            "value_persisted": False,
        },
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )

    completed = 0
    invalid_outputs = 0
    technical_failures = 0
    actual_cost = Decimal("0")
    hard_limit = Decimal(
        str(freeze["preflight"]["hard_budget_limit_usd"])
    )
    for case in cases:
        prediction = _request_case(
            client=client,
            case=case,
            monotonic_fn=monotonic_fn,
        )
        if prediction["status"] == "completed":
            completed += 1
        elif prediction["status"] == "invalid_output":
            invalid_outputs += 1
        else:
            technical_failures += 1
        if prediction.get("cost_usd") is not None:
            actual_cost += Decimal(str(prediction["cost_usd"]))
        if actual_cost > hard_limit:
            raise ExtractionExecutionError(
                "extraction-v1 exceeded its frozen hard budget"
            )
        _write_jsonl_row(predictions_path, prediction)

    report = score_predictions(
        input_rows=cases,
        truth_rows=truth_rows,
        prediction_rows=_read_jsonl(predictions_path),
    )
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
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
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    return {
        "report": report,
        "recorded_cost_usd": float(actual_cost),
        "artifacts": {
            "predictions": str(predictions_path.relative_to(REPO_ROOT)),
            "report": str(report_path.relative_to(REPO_ROOT)),
            "run_manifest": str(manifest_path.relative_to(REPO_ROOT)),
        },
    }


def rescore_saved_run() -> dict[str, object]:
    verify_configuration_freeze()
    predictions_path = OUTPUT_DIR / PREDICTIONS_FILE
    original_report_path = OUTPUT_DIR / REPORT_FILE
    original_manifest_path = OUTPUT_DIR / RUN_MANIFEST_FILE
    rescored_report_path = OUTPUT_DIR / RESCORED_REPORT_FILE
    rescore_manifest_path = OUTPUT_DIR / RESCORE_MANIFEST_FILE
    required = (
        predictions_path,
        original_report_path,
        original_manifest_path,
    )
    if any(not path.is_file() for path in required):
        raise FileNotFoundError(
            "completed extraction-v1 artifacts are required for rescore"
        )
    if rescored_report_path.exists() or rescore_manifest_path.exists():
        raise FileExistsError(
            "extraction-v1 rescore artifacts already exist; "
            "refusing overwrite"
        )

    cases = _read_jsonl(DEFAULT_DATASET_DIR / MODEL_INPUTS_FILE)
    truth_rows = _read_jsonl(DEFAULT_DATASET_DIR / TRUTH_FILE)
    prediction_rows = _read_jsonl(predictions_path)
    rebuilt = rebuild_saved_decisions(
        input_rows=cases,
        prediction_rows=prediction_rows,
    )
    report = score_predictions(
        input_rows=cases,
        truth_rows=truth_rows,
        prediction_rows=rebuilt,
    )
    rescored_report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    comparator_path = Path(__file__).with_name(
        "ai_qa_extraction_compare.py"
    )
    manifest = {
        "schema_version": "1.0",
        "status": "completed",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "reason": (
            "The original scorer did not normalize valid exact quotes with "
            "whitespace-separated labels, bare Berlin postal codes, or "
            "Stockwerk floor labels."
        ),
        "development_tuning": True,
        "api_calls_made": 0,
        "additional_cost_usd": 0,
        "source_artifacts": {
            "predictions_sha256": _sha256_file(predictions_path),
            "original_report_sha256": _sha256_file(
                original_report_path
            ),
            "original_run_manifest_sha256": _sha256_file(
                original_manifest_path
            ),
        },
        "scorer": {
            "version": SCORER_VERSION,
            "comparator_sha256": _sha256_file(comparator_path),
        },
        "result": {
            "report_sha256": _sha256_file(rescored_report_path),
            "gate_status": report["gate_decision"]["status"],
            "new_600_case_evaluation_authorized": report[
                "gate_decision"
            ]["new_600_case_evaluation_authorized"],
        },
        "boundary": (
            "This development rescore reuses saved model outputs and is not "
            "final 600-case evidence."
        ),
    }
    rescore_manifest_path.write_text(
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
        "api_calls_made": 0,
        "additional_cost_usd": 0,
        "artifacts": {
            "report": str(
                rescored_report_path.relative_to(REPO_ROOT)
            ),
            "manifest": str(
                rescore_manifest_path.relative_to(REPO_ROOT)
            ),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Freeze, verify, or execute the one-shot extraction-v1 "
            "development run."
        ),
    )
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--print-freeze", action="store_true")
    actions.add_argument("--verify-freeze", action="store_true")
    actions.add_argument("--execute", action="store_true")
    actions.add_argument("--rescore", action="store_true")
    args = parser.parse_args()

    if args.print_freeze:
        result: object = build_configuration_freeze()
    elif args.verify_freeze:
        result = verify_configuration_freeze()
    elif args.execute:
        result = execute_frozen_run()
    else:
        result = rescore_saved_run()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
