from __future__ import annotations

import argparse
import hashlib
import json
from decimal import Decimal, ROUND_CEILING
from pathlib import Path
from typing import Any, Mapping

from eval.ai_qa_extraction_contract import (
    EXTRACTION_PROMPT_VERSION,
    MODEL_OUTPUT_JSON_SCHEMA,
    SYSTEM_INSTRUCTIONS,
    render_case_input,
)
from eval.ai_qa_review_development import (
    DEFAULT_OUTPUT_DIR as DEFAULT_DATASET_DIR,
)
from eval.ai_qa_review_development import (
    MANIFEST_FILE,
    MODEL_INPUTS_FILE,
    TRUTH_FILE,
    verify_review_development,
)


RUNNER_VERSION = "extraction-plan-v2"
MODEL = "gpt-5.6-terra"
REASONING_EFFORT = "high"
SERVICE_TIER = "default"
MAX_OUTPUT_TOKENS = 768
RETRIES = 0
TIMEOUT_SECONDS = 60.0
STORE = False

INPUT_PRICE_PER_1M = Decimal("2.50")
CACHED_INPUT_PRICE_PER_1M = Decimal("0.25")
CACHE_WRITE_PRICE_PER_1M = Decimal("3.125")
OUTPUT_PRICE_PER_1M = Decimal("15.00")
PRICING_OBSERVED_DATE = "2026-07-30"
PRICING_SOURCE = "https://developers.openai.com/api/docs/pricing"

DEFAULT_PLAN_PATH = (
    Path(__file__).with_name("runs")
    / "extraction-v1-development-dry-run.json"
)

_FORBIDDEN_REQUEST_KEYS = (
    "case_id",
    "parser_snapshot",
    "case_type",
    "corrupted_field",
    "expected_value",
    "corrupted_value",
    "corruption_type",
    "truth",
)


class ExtractionRunnerError(RuntimeError):
    """The extraction-v1 development runner cannot proceed safely."""


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as artifact:
        for chunk in iter(lambda: artifact.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
    ]


def _round_up_cents(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_CEILING)


def _cost_usd(
    *,
    input_tokens: int,
    output_tokens: int,
    input_price_per_1m: Decimal = INPUT_PRICE_PER_1M,
) -> Decimal:
    return (
        Decimal(input_tokens) * input_price_per_1m
        + Decimal(output_tokens) * OUTPUT_PRICE_PER_1M
    ) / Decimal(1_000_000)


def _verify_request_hygiene(
    *,
    case: Mapping[str, object],
    rendered_input: str,
) -> None:
    for forbidden in _FORBIDDEN_REQUEST_KEYS:
        if f'"{forbidden}"' in rendered_input:
            raise ExtractionRunnerError(
                f"hidden answer field leaked into model input: {forbidden}"
            )
    if str(case["case_id"]) in rendered_input:
        raise ExtractionRunnerError("case ID leaked into model input")
    payload = json.loads(rendered_input)
    if set(payload) != {"raw_listing_text"}:
        raise ExtractionRunnerError(
            "model input must contain raw listing text only"
        )
    if payload["raw_listing_text"] != case["raw_text"]:
        raise ExtractionRunnerError("raw listing text changed during rendering")


def build_extraction_development_dry_run(
    *,
    dataset_dir: Path = DEFAULT_DATASET_DIR,
) -> dict[str, object]:
    """Build a deterministic extraction-v1 plan without network access."""

    manifest = verify_review_development(dataset_dir)
    input_path = dataset_dir / MODEL_INPUTS_FILE
    truth_path = dataset_dir / TRUTH_FILE
    cases = _read_jsonl(input_path)

    rendered_inputs: list[str] = []
    for case in cases:
        rendered = render_case_input(case)
        _verify_request_hygiene(case=case, rendered_input=rendered)
        rendered_inputs.append(rendered)

    system_bytes_per_request = len(SYSTEM_INSTRUCTIONS.encode("utf-8"))
    user_input_bytes = sum(
        len(rendered.encode("utf-8"))
        for rendered in rendered_inputs
    )
    input_token_upper_bound = (
        system_bytes_per_request * len(cases)
        + user_input_bytes
    )
    output_token_upper_bound = MAX_OUTPUT_TOKENS * len(cases)
    worst_case_cost = _cost_usd(
        input_tokens=input_token_upper_bound,
        output_tokens=output_token_upper_bound,
        input_price_per_1m=CACHE_WRITE_PRICE_PER_1M,
    )
    hard_budget = _round_up_cents(worst_case_cost)

    return {
        "runner_version": RUNNER_VERSION,
        "mode": "dry_run",
        "network_calls_made": 0,
        "credential_read": False,
        "dataset": {
            "split": manifest["split"],
            "case_count": len(cases),
            "model_inputs_file": MODEL_INPUTS_FILE,
            "model_inputs_sha256": _sha256_file(input_path),
            "truth_file": TRUTH_FILE,
            "truth_sha256": _sha256_file(truth_path),
            "manifest_file": MANIFEST_FILE,
            "manifest_sha256": _sha256_file(dataset_dir / MANIFEST_FILE),
            "reused_development_set": True,
        },
        "configuration": {
            "model": MODEL,
            "reasoning_effort": REASONING_EFFORT,
            "prompt_version": EXTRACTION_PROMPT_VERSION,
            "max_output_tokens": MAX_OUTPUT_TOKENS,
            "retries": RETRIES,
            "service_tier": SERVICE_TIER,
            "timeout_seconds": TIMEOUT_SECONDS,
            "store": STORE,
            "strict_structured_outputs": True,
            "model_receives_parser_snapshot": False,
        },
        "hashes": {
            "prompt_sha256": _sha256_bytes(
                SYSTEM_INSTRUCTIONS.encode("utf-8")
            ),
            "output_schema_sha256": _sha256_bytes(
                _canonical_json(MODEL_OUTPUT_JSON_SCHEMA).encode("utf-8")
            ),
            "rendered_inputs_sha256": _sha256_bytes(
                "\n".join(rendered_inputs).encode("utf-8")
            ),
        },
        "requests": {
            "case_requests": len(cases),
            "retry_requests_reserved": RETRIES * len(cases),
            "maximum_responses_api_requests": (
                len(cases) * (RETRIES + 1)
            ),
            "model_availability_checks": 1,
            "maximum_total_api_calls": 1 + len(cases) * (RETRIES + 1),
        },
        "preflight": {
            "method": (
                "UTF-8 bytes as a conservative input-token upper bound; "
                "maximum output tokens reserved for every case; no cache "
                "discount assumed; all input priced at the higher cache-write "
                "rate"
            ),
            "input_token_upper_bound": input_token_upper_bound,
            "output_token_upper_bound": output_token_upper_bound,
            "worst_case_cost_usd": str(
                worst_case_cost.quantize(Decimal("0.000001"))
            ),
            "hard_budget_limit_usd": str(hard_budget),
        },
        "pricing": {
            "input_per_1m_usd": str(INPUT_PRICE_PER_1M),
            "cached_input_per_1m_usd": str(CACHED_INPUT_PRICE_PER_1M),
            "cache_write_per_1m_usd": str(CACHE_WRITE_PRICE_PER_1M),
            "output_per_1m_usd": str(OUTPUT_PRICE_PER_1M),
            "observed_date": PRICING_OBSERVED_DATE,
            "source": PRICING_SOURCE,
            "must_refresh_before_execute": True,
        },
        "development_targets": {
            "successful_checks": "at least 119/120",
            "errors_detected": "at least 68/70",
            "correct_fields": "at least 68/70",
            "clean_false_alerts": "at most 1/50",
            "rooms_correct_field": "at least 19/20",
            "wbs_correct_field": "10/10",
            "rent_kalt_correct_field": "10/10",
            "address_postal_code_correct_field": "10/10",
            "district_correct_field": "8/8",
            "floor_correct_field": "6/6",
            "rent_warm_correct_field": "6/6",
            "must_improve_previous_best": (
                "more than 66/70 correct fields and more than 17/20 rooms, "
                "with 8/8 district and no false-alert regression"
            ),
        },
        "execution_guard": {
            "status": "blocked",
            "reason": (
                "This artifact only proves local readiness. It does not "
                "authorize an API call."
            ),
            "next_required_artifact": (
                "eval/runs/extraction-v1-development-configuration-freeze.json"
            ),
        },
        "boundaries": {
            "development_only": True,
            "final_600_case_evidence": False,
            "product_runtime_modified": False,
            "consumed_holdout_reused": False,
        },
    }


def verify_dry_run_plan(
    path: Path = DEFAULT_PLAN_PATH,
) -> dict[str, object]:
    stored = json.loads(path.read_text(encoding="utf-8"))
    expected = build_extraction_development_dry_run()
    if stored != expected:
        raise ValueError(
            "extraction-v1 dry-run plan does not match current inputs"
        )
    return stored


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect the extraction-v1 development plan without a network call."
        ),
    )
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    if args.execute:
        raise ExtractionRunnerError(
            "API execution is disabled until a separate configuration freeze "
            "and execution module exist"
        )
    plan = (
        verify_dry_run_plan()
        if args.verify_only
        else build_extraction_development_dry_run()
    )
    print(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
