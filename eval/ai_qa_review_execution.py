from __future__ import annotations

import argparse
import json
import time
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol

import openai
from dotenv import dotenv_values
from openai import OpenAI

from eval.ai_qa_review_development import (
    DEFAULT_OUTPUT_DIR as DEFAULT_DATASET_DIR,
)
from eval.ai_qa_review_development import MODEL_INPUTS_FILE, TRUTH_FILE
from eval.ai_qa_review_runner import (
    CACHED_INPUT_PRICE_PER_1M,
    INPUT_PRICE_PER_1M,
    MODEL,
    OUTPUT_PRICE_PER_1M,
    PRICING_OBSERVED_DATE,
    PRICING_SOURCE,
    REASONING_EFFORT,
    RETRIES,
    RUNNER_VERSION,
    SERVICE_TIER,
    STORE,
    TIMEOUT_SECONDS,
    _PROFILES,
    _canonical_json,
    _read_jsonl,
    _sha256_bytes,
    _sha256_file,
    build_review_development_dry_run,
    verify_dry_run_plan,
)
from eval.ai_qa_review_scorer import score_review_prediction_files


EXECUTION_VERSION = "review-execution-v1"
FREEZE_SCHEMA_VERSION = "1.0"
RUN_MANIFEST_SCHEMA_VERSION = "1.0"
PREDICTIONS_FILE = "predictions.jsonl"
RUN_MANIFEST_FILE = "run_manifest.json"
REPORT_FILE = "report.json"

REPO_ROOT = Path(__file__).resolve().parents[1]
EVAL_ROOT = Path(__file__).resolve().parent
EVAL_ENV_PATH = REPO_ROOT / ".env.eval.local"
FREEZE_PATH = (
    EVAL_ROOT
    / "runs"
    / "review-v1-development-configuration-freeze.json"
)
COMPARISON_DIR = EVAL_ROOT / "runs" / "review-v1-development-comparison"
COMPARISON_PATH = COMPARISON_DIR / "comparison.json"

PROFILE_OUTPUT_DIRS = {
    name: REPO_ROOT / str(config["future_output_dir"])
    for name, config in _PROFILES.items()
}


class ReviewExecutionError(RuntimeError):
    """The frozen development comparison cannot proceed safely."""


class ResponsesClient(Protocol):
    models: object
    responses: object


def _ensure_inside_eval(path: Path) -> Path:
    resolved = path.resolve()
    if resolved != EVAL_ROOT and EVAL_ROOT not in resolved.parents:
        raise ReviewExecutionError("artifact path must stay inside eval/")
    return resolved


def _profile_freeze(name: str, plan: Mapping[str, object]) -> dict[str, object]:
    profile = plan["paired_comparison"]["profiles"][name]
    return {
        "configuration": profile["configuration"],
        "hashes": profile["hashes"],
        "requests": profile["requests"],
        "preflight": profile["preflight"],
        "output_dir": str(
            PROFILE_OUTPUT_DIRS[name].relative_to(REPO_ROOT)
        ),
        "run_count_limit": 1,
    }


def build_configuration_freeze() -> dict[str, object]:
    plan = verify_dry_run_plan()
    return {
        "schema_version": FREEZE_SCHEMA_VERSION,
        "status": "paired_development_authorized_once",
        "created_on": PRICING_OBSERVED_DATE,
        "execution_version": EXECUTION_VERSION,
        "dry_run_runner_version": RUNNER_VERSION,
        "dry_run_plan_sha256": _sha256_file(
            EVAL_ROOT / "runs" / "review-v1-development-dry-run.json"
        ),
        "dataset": plan["dataset"],
        "pricing": {
            **plan["pricing"],
            "must_refresh_before_execute": False,
            "verified_against_official_docs": True,
        },
        "combined_hard_budget_limit_usd": plan[
            "combined_hard_budget_limit_usd"
        ],
        "profiles": {
            name: _profile_freeze(name, plan)
            for name in ("baseline", "candidate")
        },
        "development_targets": plan["development_targets"],
        "authorization": {
            "model_availability_checks": 1,
            "paired_runs": 1,
            "total_case_requests": 240,
            "retries": 0,
            "resume_or_overwrite": False,
            "final_600_case_run": False,
        },
        "boundaries": plan["boundaries"],
    }


def write_configuration_freeze(
    path: Path = FREEZE_PATH,
) -> dict[str, object]:
    path = _ensure_inside_eval(path)
    if path.exists():
        raise FileExistsError("review-v1 configuration freeze already exists")
    freeze = build_configuration_freeze()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(freeze, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    verify_configuration_freeze(path)
    return freeze


def verify_configuration_freeze(
    path: Path = FREEZE_PATH,
) -> dict[str, object]:
    path = _ensure_inside_eval(path)
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReviewExecutionError(
            "valid review-v1 configuration freeze is required"
        ) from exc
    expected = build_configuration_freeze()
    if stored != expected:
        raise ReviewExecutionError(
            "configuration freeze differs from current code or dataset"
        )
    return stored


def load_eval_api_key() -> str:
    values = dotenv_values(EVAL_ENV_PATH)
    api_key = values.get("OPENAI_API_KEY")
    if not isinstance(api_key, str) or not api_key.strip():
        raise ReviewExecutionError(
            "OPENAI_API_KEY is missing from .env.eval.local"
        )
    return api_key.strip()


def _new_openai_client(api_key: str) -> ResponsesClient:
    return OpenAI(api_key=api_key, base_url="https://api.openai.com/v1")


def verify_model_availability(
    client: ResponsesClient,
    model: str = MODEL,
) -> None:
    try:
        record = client.models.retrieve(model)
    except Exception as exc:
        failure_type = _classify_api_exception(exc)
        raise ReviewExecutionError(
            f"model availability check failed: {failure_type}"
        ) from None
    if getattr(record, "id", None) != model:
        raise ReviewExecutionError(
            "model availability check returned a different model ID"
        )


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
        "output_tokens": int(getattr(usage, "output_tokens", 0)),
        "reasoning_tokens": int(
            getattr(output_details, "reasoning_tokens", 0) or 0
        ),
    }
    if any(value < 0 for value in values.values()):
        raise ReviewExecutionError("response usage contains negative values")
    if (
        values["cached_input_tokens"] > values["input_tokens"]
        or values["reasoning_tokens"] > values["output_tokens"]
    ):
        raise ReviewExecutionError(
            "response usage details exceed their totals"
        )
    return values


def calculate_cost_usd(usage: Mapping[str, int]) -> Decimal:
    uncached = Decimal(
        usage["input_tokens"] - usage["cached_input_tokens"]
    )
    cached = Decimal(usage["cached_input_tokens"])
    output = Decimal(usage["output_tokens"])
    return (
        uncached * INPUT_PRICE_PER_1M
        + cached * CACHED_INPUT_PRICE_PER_1M
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
    profile_name: str,
    case: Mapping[str, object],
    monotonic_fn: Callable[[], float] = time.monotonic,
) -> dict[str, object]:
    profile = _PROFILES[profile_name]
    started = monotonic_fn()
    try:
        response = client.responses.create(
            model=MODEL,
            reasoning={"effort": REASONING_EFFORT},
            instructions=profile["system_instructions"],
            input=profile["render"](case),
            text={
                "format": {
                    "type": "json_schema",
                    "name": f"flatfeed_parser_{profile_name}",
                    "strict": True,
                    "schema": profile["schema"],
                }
            },
            max_output_tokens=profile["max_output_tokens"],
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
            "latency_mode": "synchronous_case",
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
    if failure_type is not None:
        return {
            "case_id": str(case["case_id"]),
            "status": "technical_failure",
            "failure": {"type": failure_type},
            "latency_ms": latency_ms,
            "latency_mode": "synchronous_case",
            "retry_count": 0,
        }

    row: dict[str, object] = {
        "case_id": str(case["case_id"]),
        "status": "completed",
        "raw_output": raw_output,
        "latency_ms": latency_ms,
        "latency_mode": "synchronous_case",
        "retry_count": 0,
    }
    usage = _usage_from_response(response)
    if usage is not None:
        row["usage"] = usage
        row["cost_usd"] = float(calculate_cost_usd(usage))
    return row


def _write_jsonl_row(path: Path, row: Mapping[str, object]) -> None:
    with path.open("a", encoding="utf-8") as artifact:
        artifact.write(_canonical_json(row) + "\n")
        artifact.flush()


def _manifest_for_profile(
    *,
    profile_name: str,
    freeze: Mapping[str, object],
    status: str,
) -> dict[str, object]:
    profile = freeze["profiles"][profile_name]
    return {
        "schema_version": RUN_MANIFEST_SCHEMA_VERSION,
        "execution_version": EXECUTION_VERSION,
        "status": status,
        "split": "review_v1_development",
        "profile": profile_name,
        "case_count": freeze["dataset"]["case_count"],
        "input": {
            "file": freeze["dataset"]["model_inputs_file"],
            "sha256": freeze["dataset"]["model_inputs_sha256"],
            "dataset_manifest_sha256": freeze["dataset"][
                "manifest_sha256"
            ],
        },
        "configuration": profile["configuration"],
        "hashes": profile["hashes"],
        "budget": {
            "hard_limit_usd": profile["preflight"][
                "hard_budget_limit_usd"
            ],
            "preflight_worst_case_usd": profile["preflight"][
                "worst_case_cost_usd"
            ],
            "input_price_per_1m": str(INPUT_PRICE_PER_1M),
            "cached_input_price_per_1m": str(
                CACHED_INPUT_PRICE_PER_1M
            ),
            "output_price_per_1m": str(OUTPUT_PRICE_PER_1M),
            "pricing_source": PRICING_SOURCE,
            "pricing_observed_date": PRICING_OBSERVED_DATE,
        },
        "credential": {
            "source": ".env.eval.local",
            "variable": "OPENAI_API_KEY",
            "value_persisted": False,
        },
        "configuration_freeze_sha256": _sha256_file(FREEZE_PATH),
        "product_boundary": (
            "Development eval only; no product-runtime integration."
        ),
    }


def _metric_numerator(
    report: Mapping[str, object],
    name: str,
) -> int:
    return int(report["metrics"][name]["numerator"])


def _focus_correct_count(
    report: Mapping[str, object],
    focus_ids: set[str],
) -> int:
    failed_ids = {
        str(row["case_id"])
        for key in ("false_negatives", "wrong_fields")
        for row in report["diagnostics"][key]
    }
    return len(focus_ids - failed_ids)


def build_comparison(
    *,
    baseline: Mapping[str, object],
    candidate: Mapping[str, object],
    truth_rows: list[dict[str, Any]],
    run_manifests: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    candidate_metrics = candidate["metrics"]
    candidate_fields = candidate["per_field"]
    focus_ids = {
        str(row["case_id"])
        for row in truth_rows
        if row["case_type"] == "corrupted"
        and row["corruption_type"]
        in {"rooms_neighbor_value", "postal_code_substitution"}
    }
    baseline_focus = _focus_correct_count(baseline, focus_ids)
    candidate_focus = _focus_correct_count(candidate, focus_ids)

    gates = {
        "successful_checks_at_least_119_of_120": (
            _metric_numerator(candidate, "successful_check_rate") >= 119
        ),
        "errors_detected_at_least_68_of_70": (
            _metric_numerator(candidate, "parser_error_detection_rate")
            >= 68
        ),
        "correct_fields_at_least_67_of_70": (
            _metric_numerator(candidate, "correct_field_detection_rate")
            >= 67
        ),
        "clean_false_alerts_at_most_1_of_50": (
            _metric_numerator(candidate, "false_alert_rate") <= 1
        ),
        "rooms_at_least_19_of_20": (
            candidate_fields["rooms"]["correct_field"] >= 19
        ),
        "wbs_10_of_10": (
            candidate_fields["wbs"]["correct_field"] == 10
        ),
        "rent_kalt_10_of_10": (
            candidate_fields["rent_kalt"]["correct_field"] == 10
        ),
        "address_postal_code_10_of_10": (
            candidate_fields["address_postal_code"]["correct_field"] == 10
        ),
        "district_8_of_8": (
            candidate_fields["district"]["correct_field"] == 8
        ),
        "floor_6_of_6": (
            candidate_fields["floor"]["correct_field"] == 6
        ),
        "rent_warm_6_of_6": (
            candidate_fields["rent_warm"]["correct_field"] == 6
        ),
        "total_correct_not_below_baseline": (
            _metric_numerator(candidate, "case_accuracy")
            >= _metric_numerator(baseline, "case_accuracy")
        ),
        "clean_false_alerts_not_above_baseline": (
            _metric_numerator(candidate, "false_alert_rate")
            <= _metric_numerator(baseline, "false_alert_rate")
        ),
        "focus_not_below_baseline": candidate_focus >= baseline_focus,
        "focus_net_recovery_when_baseline_misses": (
            baseline_focus == len(focus_ids)
            or candidate_focus > baseline_focus
        ),
    }
    return {
        "schema_version": "1.0",
        "status": "pass" if all(gates.values()) else "fail",
        "split": "review_v1_development",
        "case_count": len(truth_rows),
        "configuration_freeze_sha256": _sha256_file(FREEZE_PATH),
        "profiles": {
            "baseline": {
                "report": baseline,
                "recorded_cost_usd": run_manifests["baseline"]["result"][
                    "recorded_cost_usd"
                ],
            },
            "candidate": {
                "report": candidate,
                "recorded_cost_usd": run_manifests["candidate"]["result"][
                    "recorded_cost_usd"
                ],
            },
        },
        "focus": {
            "case_count": len(focus_ids),
            "baseline_correct": baseline_focus,
            "candidate_correct": candidate_focus,
        },
        "gates": gates,
        "all_gates_passed": all(gates.values()),
        "boundaries": {
            "development_only": True,
            "final_600_case_evidence": False,
            "product_runtime_modified": False,
        },
    }


def _assert_artifacts_absent() -> None:
    targets = [COMPARISON_PATH]
    for output_dir in PROFILE_OUTPUT_DIRS.values():
        targets.extend(
            [
                output_dir / PREDICTIONS_FILE,
                output_dir / RUN_MANIFEST_FILE,
                output_dir / "reports" / REPORT_FILE,
            ]
        )
    if any(path.exists() for path in targets):
        raise FileExistsError(
            "review-v1 run artifacts already exist; refusing overwrite"
        )


def execute_frozen_pair(
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

    reports: dict[str, Mapping[str, object]] = {}
    manifests: dict[str, Mapping[str, object]] = {}
    paths: dict[str, dict[str, str]] = {}
    for profile_name in ("baseline", "candidate"):
        output_dir = _ensure_inside_eval(PROFILE_OUTPUT_DIRS[profile_name])
        output_dir.mkdir(parents=True, exist_ok=False)
        predictions_path = output_dir / PREDICTIONS_FILE
        manifest_path = output_dir / RUN_MANIFEST_FILE
        manifest = _manifest_for_profile(
            profile_name=profile_name,
            freeze=freeze,
            status="running",
        )
        manifest["started_at"] = datetime.now(timezone.utc).isoformat()
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
        technical_failures = 0
        actual_cost = Decimal("0")
        hard_limit = Decimal(
            freeze["profiles"][profile_name]["preflight"][
                "hard_budget_limit_usd"
            ]
        )
        for case in cases:
            prediction = _request_case(
                client=client,
                profile_name=profile_name,
                case=case,
                monotonic_fn=monotonic_fn,
            )
            if prediction["status"] == "completed":
                completed += 1
            else:
                technical_failures += 1
            if prediction.get("cost_usd") is not None:
                actual_cost += Decimal(str(prediction["cost_usd"]))
            if actual_cost > hard_limit:
                raise ReviewExecutionError(
                    f"{profile_name} exceeded its frozen hard budget"
                )
            _write_jsonl_row(predictions_path, prediction)

        manifest["status"] = "completed"
        manifest["completed_at"] = datetime.now(timezone.utc).isoformat()
        manifest["result"] = {
            "completed_cases": completed,
            "technical_failures": technical_failures,
            "recorded_cost_usd": float(actual_cost),
            "predictions_file": PREDICTIONS_FILE,
            "predictions_sha256": _sha256_file(predictions_path),
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

        report = score_review_prediction_files(
            profile=profile_name,
            model_inputs_path=DEFAULT_DATASET_DIR / MODEL_INPUTS_FILE,
            truth_path=DEFAULT_DATASET_DIR / TRUTH_FILE,
            predictions_path=predictions_path,
        )
        report_dir = output_dir / "reports"
        report_dir.mkdir()
        report_path = report_dir / REPORT_FILE
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
        reports[profile_name] = report
        manifests[profile_name] = manifest
        paths[profile_name] = {
            "predictions": str(predictions_path.relative_to(REPO_ROOT)),
            "run_manifest": str(manifest_path.relative_to(REPO_ROOT)),
            "report": str(report_path.relative_to(REPO_ROOT)),
        }

    comparison = build_comparison(
        baseline=reports["baseline"],
        candidate=reports["candidate"],
        truth_rows=truth_rows,
        run_manifests=manifests,
    )
    COMPARISON_DIR.mkdir(parents=True, exist_ok=False)
    COMPARISON_PATH.write_text(
        json.dumps(
            comparison,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "comparison": comparison,
        "artifacts": {
            **paths,
            "comparison": str(COMPARISON_PATH.relative_to(REPO_ROOT)),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Freeze or execute the paired review-v1 development comparison."
        ),
    )
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--write-freeze", action="store_true")
    actions.add_argument("--verify-freeze", action="store_true")
    actions.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    if args.write_freeze:
        result: object = write_configuration_freeze()
    elif args.verify_freeze:
        result = verify_configuration_freeze()
    else:
        result = execute_frozen_pair()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
